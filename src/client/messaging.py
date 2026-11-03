"""Mensageria E2E do cliente: junta a rede (connection.py) e o estado cripto (peers.py).

Fluxo:
    conectar() -> REGISTER -> [handshake] -> CLIENT_LIST -> escutar()
    enviar_texto()  : preparar_envio -> RELAY(payload = quadro E2E)
    RELAY recebido  : confere sender_id -> processar_recebimento -> evento "mensagem"

Politica de logs: nada aqui imprime chaves, Z, salt, nonce ou texto. O texto
decifrado so sai pelo evento "mensagem", que a interface mostra na tela do chat.
Rejeicoes geram o evento "rejeitada" apenas com o client_id e o motivo.
"""

import asyncio
import hashlib
import uuid
from dataclasses import dataclass

from src.client import connection
from src.client.peers import ErroMensagem, ErroReplay, criar_estado_peer, preparar_envio, processar_recebimento
from src.common.constants import TAMANHO_ID, TAMANHO_NONCE
from src.common.framing import ErroQuadro
from src.common.protocol import ErroProtocolo, decodificar_chave_publica, decodificar_conteudo, validar_id_cliente
from src.crypto.key_derivation import SALT_PROVISORIO, gerar_par_efemero


class ErroCliente(Exception):
    pass


@dataclass(frozen=True)
class Evento:
    """tipo: "entrou" | "saiu" | "mensagem" | "rejeitada" | "desconectado"."""
    tipo: str
    id_peer: str | None = None
    texto: str | None = None   # texto decifrado ("mensagem") ou motivo ("rejeitada"/"desconectado")


def impressao_digital(chave_publica):
    """Fingerprint curto (SHA-256) de uma chave publica: pode ir para tela/log."""
    return hashlib.sha256(chave_publica).hexdigest()[:16]


class Cliente:
    def __init__(self, id_cliente=None):
        self.id_cliente = validar_id_cliente(id_cliente) if id_cliente else str(uuid.uuid4())
        self.id_bytes = uuid.UUID(self.id_cliente).bytes
        # Par efemero novo a cada Cliente: reconectar = criar outro Cliente = chaves novas.
        self._chave_privada, self.chave_publica = gerar_par_efemero()
        self._salt = None
        self.peers = {}               # client_id (texto) -> EstadoPeer
        self.eventos = asyncio.Queue()
        self._leitor = None
        self._escritor = None
        self._trava_envio = asyncio.Lock()

    def __repr__(self):
        return f"Cliente(id_cliente={self.id_cliente!r}, peers={len(self.peers)})"

    # ------------------------------------------------------------------ conexao

    async def conectar(self, endereco=connection.ENDERECO_PADRAO, porta=connection.PORTA_PADRAO):
        """Abre a conexao, registra, conclui o handshake e carrega a lista de peers."""
        self._leitor, self._escritor = await connection.conectar(endereco, porta)
        try:
            await connection.registrar(self._escritor, self.id_cliente, self.chave_publica)
            self._salt = await self._handshake()
            mensagem = await connection.receber_mensagem(self._leitor)
            if mensagem is None or mensagem.get("type") != "CLIENT_LIST":
                raise ErroCliente("expected CLIENT_LIST after REGISTER")
            clientes = mensagem.get("clients")
            if not isinstance(clientes, list):
                raise ErroProtocolo("invalid CLIENT_LIST")
            for item in clientes:
                if not isinstance(item, dict):
                    raise ErroProtocolo("invalid CLIENT_LIST entry")
                self._adicionar_peer(item.get("client_id"), item.get("client_public_key"))
        except BaseException:
            await self.fechar()
            raise

    async def _handshake(self):
        """Ponto de integracao com o handshake do Integrante A (Etapa 10).

        TODO handshake: ler a resposta do servidor (pk_S, certificado, assinatura,
        salt_srv), validar o certificado contra certs/server.crt e a assinatura
        RSA-PSS sobre SHA256(pk_server || pk_client || client_id || salt). Se
        falhar, lancar ErroCliente (conectar() fecha a conexao). Retornar salt_srv.
        """
        return SALT_PROVISORIO

    async def fechar(self):
        if self._escritor is not None:
            await connection.fechar(self._escritor)
        # Esquece todo o material cripto da sessao.
        self.peers.clear()
        self._salt = None

    # ------------------------------------------------------------------ envio

    def resolver_peer(self, prefixo):
        """Encontra o client_id de um peer pelo id completo ou por um prefixo unico."""
        candidatos = [id_peer for id_peer in self.peers if id_peer.startswith(prefixo.lower())]
        if not prefixo or not candidatos:
            raise ErroCliente("unknown peer")
        if len(candidatos) > 1:
            raise ErroCliente("ambiguous peer prefix")
        return candidatos[0]

    async def enviar_texto(self, id_peer, texto):
        """Cifra o texto para o peer e envia pelo relay. Retorna o quadro E2E enviado."""
        estado = self.peers.get(id_peer)
        if estado is None:
            raise ErroCliente("unknown peer")
        dados = texto.encode("utf-8") if isinstance(texto, str) else texto
        async with self._trava_envio:
            quadro = preparar_envio(estado, self.id_bytes, dados)
            await connection.enviar_relay(self._escritor, id_peer, quadro)
        return quadro

    # ------------------------------------------------------------------ recebimento

    async def escutar(self):
        """Le o socket ate o servidor fechar; publica os eventos em self.eventos.

        Um quadro TCP/JSON malformado vindo do servidor encerra a conexao com
        seguranca (evento "desconectado" com o motivo).
        """
        motivo = "server closed the connection"
        try:
            while True:
                mensagem = await connection.receber_mensagem(self._leitor)
                if mensagem is None:
                    break
                self.processar_mensagem(mensagem)
        except (ErroQuadro, ErroProtocolo, ErroCliente) as erro:
            motivo = f"protocol error: {erro}"
        except (ConnectionError, OSError, asyncio.IncompleteReadError) as erro:
            motivo = f"connection lost: {type(erro).__name__}"
        finally:
            await self.fechar()
            self.eventos.put_nowait(Evento("desconectado", texto=motivo))

    def processar_mensagem(self, mensagem):
        """Trata uma mensagem de controle ja decodificada e publica o evento resultante."""
        tipo = mensagem.get("type")
        if tipo == "CLIENT_JOINED":
            id_peer = self._adicionar_peer(mensagem.get("client_id"), mensagem.get("client_public_key"))
            self.eventos.put_nowait(Evento("entrou", id_peer))
        elif tipo == "CLIENT_LEFT":
            id_peer = validar_id_cliente(mensagem.get("client_id"))
            if self.peers.pop(id_peer, None) is not None:
                self.eventos.put_nowait(Evento("saiu", id_peer))
        elif tipo == "RELAY":
            self._receber_relay(mensagem)
        else:
            raise ErroProtocolo("unexpected message type from server")

    def _adicionar_peer(self, id_peer, chave_publica_b64):
        id_peer = validar_id_cliente(id_peer)
        chave_publica = decodificar_chave_publica(chave_publica_b64)
        if id_peer == self.id_cliente:
            raise ErroProtocolo("server announced our own client_id")
        try:
            estado = criar_estado_peer(
                self._chave_privada, self.id_bytes, uuid.UUID(id_peer).bytes, chave_publica, self._salt
            )
        except ValueError as erro:   # ex.: chave X25519 de ordem baixa
            raise ErroProtocolo("invalid peer public key") from erro
        # Peer novo (ou reconectado com outro par efemero): estado sempre recomeca.
        self.peers[id_peer] = estado
        return id_peer

    def _receber_relay(self, mensagem):
        id_remetente = None
        try:
            id_remetente = validar_id_cliente(mensagem.get("sender_id"))
            estado = self.peers.get(id_remetente)
            if estado is None:
                raise ErroMensagem("unknown sender")
            if mensagem.get("recipient_id") != self.id_cliente:
                raise ErroMensagem("frame addressed to another client")
            quadro = decodificar_conteudo(mensagem.get("payload"))
            # O sender_id do JSON e posto pelo servidor; o do quadro e autenticado
            # pela tag. Os dois precisam coincidir.
            if quadro[TAMANHO_NONCE:TAMANHO_NONCE + TAMANHO_ID] != estado.id_peer:
                raise ErroMensagem("sender_id mismatch between relay and frame")
            texto = processar_recebimento(estado, self.id_bytes, quadro)
        except ErroReplay as erro:
            self.eventos.put_nowait(Evento("rejeitada", id_remetente, f"replay: {erro}"))
            return
        except (ErroMensagem, ErroProtocolo) as erro:
            self.eventos.put_nowait(Evento("rejeitada", id_remetente, str(erro)))
            return
        self.eventos.put_nowait(Evento("mensagem", id_remetente, texto.decode("utf-8", errors="replace")))
