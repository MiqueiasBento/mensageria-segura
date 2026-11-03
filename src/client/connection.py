"""Camada de rede do cliente: conexao TCP e mensagens JSON de controle.

O canal autentica o envelope; o payload do RELAY chega aqui como bytes opacos
(o quadro E2E montado em src/client/peers.py).
"""

import asyncio
import base64

from src.common.framing import escrever_quadro, ler_quadro
from src.common.protocol import codificar_mensagem, decodificar_mensagem, validar_id_cliente

ENDERECO_PADRAO = "127.0.0.1"
PORTA_PADRAO = 8000


async def conectar(endereco=ENDERECO_PADRAO, porta=PORTA_PADRAO):
    """Retorna (leitor, escritor) da conexao TCP com o servidor."""
    return await asyncio.open_connection(endereco, porta)


async def registrar(escritor, id_cliente, chave_publica):
    """Envia REGISTER com o client_id (UUIDv4 em texto) e a chave publica X25519 (32 bytes)."""
    validar_id_cliente(id_cliente)
    if not isinstance(chave_publica, bytes) or len(chave_publica) != 32:
        raise ValueError("public key must contain 32 bytes")
    await escrever_quadro(escritor, codificar_mensagem({
        "type": "REGISTER",
        "client_id": id_cliente,
        "client_public_key": base64.b64encode(chave_publica).decode("ascii"),
    }))


async def receber_mensagem(leitor, canal=None):
    """Retorna a proxima mensagem de controle (dict) ou None quando o servidor fecha.

    Lanca ErroQuadro / ErroProtocolo se o servidor enviar algo malformado.
    """
    dados = await ler_quadro(leitor)
    if dados is None:
        return None
    mensagem = decodificar_mensagem(dados)
    return canal.desempacotar(mensagem) if canal is not None else mensagem


async def enviar_relay(escritor, id_destinatario, payload, canal):
    """Pede ao servidor para encaminhar o payload (bytes opacos) ao destinatario."""
    validar_id_cliente(id_destinatario)
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("payload must be non-empty bytes")
    await escrever_quadro(escritor, codificar_mensagem(canal.empacotar({
        "type": "RELAY",
        "recipient_id": id_destinatario,
        "payload": base64.b64encode(payload).decode("ascii"),
    })))


async def fechar(escritor):
    escritor.close()
    try:
        await escritor.wait_closed()
    except (ConnectionError, OSError):
        pass
