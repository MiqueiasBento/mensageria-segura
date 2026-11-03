"""Handshake, diretório autenticado e ciclo da conexão TCP."""

import asyncio

from src.common.framing import ErroQuadro, ler_quadro, escrever_quadro
from src.common.protocol import (
    ErroProtocolo, decodificar_mensagem, decodificar_chave_publica,
    codificar_mensagem, validar_id_cliente,
)
from src.crypto.handshake import criar_handshake
from src.server.relay import encaminhar

TEMPO_HANDSHAKE = 10
TEMPO_ESCRITA = 5


async def enviar(sessao, mensagem):
    async with sessao.trava_envio:
        try:
            async with asyncio.timeout(TEMPO_ESCRITA):
                await escrever_quadro(sessao.escritor, codificar_mensagem(sessao.canal.empacotar(mensagem)))
        except (ConnectionError, OSError, TimeoutError):
            sessao.escritor.close()
            raise


async def avisar(participantes, mensagem):
    for participante in participantes:
        try:
            await enviar(participante, mensagem)
        except (ConnectionError, OSError, TimeoutError):
            # O handler da conexão encerrada fará a remoção do registro.
            continue


async def atender_cliente(leitor, escritor, sessoes, identidade, salt):
    endereco = escritor.get_extra_info("peername")
    print(f"Cliente conectado: {endereco}")
    sessao = None
    try:
        async with asyncio.timeout(TEMPO_HANDSHAKE):
            dados = await ler_quadro(leitor)
            if dados is None:
                return
            registro = decodificar_mensagem(dados)
            if registro["type"] != "REGISTER":
                raise ErroProtocolo("primeira mensagem deve ser REGISTER")
            id_cliente = validar_id_cliente(registro.get("client_id"))
            publica = decodificar_chave_publica(registro.get("client_public_key"))
            resposta, canal = criar_handshake(identidade, publica, id_cliente, salt)
            await escrever_quadro(escritor, codificar_mensagem(resposta))
            dados = await ler_quadro(leitor)
            if dados is None or canal.desempacotar(decodificar_mensagem(dados)) != {"type": "READY"}:
                raise ErroProtocolo("confirmação do handshake ausente ou inválida")

        # Nenhuma conexão aparece no diretório antes de provar posse da chave.
        async with sessoes.trava:
            participantes = sessoes.listar_clientes()
            sessao = sessoes.registrar_cliente(id_cliente, registro["client_public_key"], escritor, canal)
            await enviar(sessao, {
                "type": "CLIENT_LIST",
                "clients": [{"client_id": participante.id_cliente, "client_public_key": participante.chave_publica} for participante in participantes],
            })
            await avisar(participantes, {
                "type": "CLIENT_JOINED", "client_id": sessao.id_cliente,
                "client_public_key": sessao.chave_publica,
            })

        while True:
            dados = await ler_quadro(leitor)
            if dados is None:
                break
            mensagem = canal.desempacotar(decodificar_mensagem(dados))
            if mensagem["type"] != "RELAY":
                raise ErroProtocolo("tipo de mensagem não permitido após o registro")
            await encaminhar(mensagem, sessao, sessoes, enviar)
    except (ErroQuadro, ErroProtocolo, ValueError) as erro:
        print(f"Erro de protocolo de {endereco}: {erro}")
    except (ConnectionError, OSError, TimeoutError, asyncio.IncompleteReadError) as erro:
        print(f"Conexão encerrada de {endereco}: {type(erro).__name__}")
    finally:
        try:
            if sessao is not None:
                async with sessoes.trava:
                    if sessoes.remover_cliente(sessao.id_cliente, escritor):
                        await avisar(sessoes.listar_clientes(), {"type": "CLIENT_LEFT", "client_id": sessao.id_cliente})
        finally:
            print(f"Cliente desconectado: {endereco}")
            escritor.close()
            try:
                await asyncio.wait_for(escritor.wait_closed(), TEMPO_ESCRITA)
            except (ConnectionError, OSError, TimeoutError):
                pass
