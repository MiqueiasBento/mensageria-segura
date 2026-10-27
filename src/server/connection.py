"""Ciclo de registro e comunicação de uma conexão TCP."""

import asyncio

from src.common.framing import ErroQuadro, ler_quadro, escrever_quadro
from src.common.protocol import (
    ErroProtocolo, decodificar_mensagem, decodificar_chave_publica, codificar_mensagem,
    validar_id_cliente,
)
from src.server.relay import encaminhar


async def enviar(sessao, mensagem):
    async with sessao.trava_envio:
        await escrever_quadro(sessao.escritor, codificar_mensagem(mensagem))


async def atender_cliente(leitor, escritor, sessoes):
    endereco = escritor.get_extra_info("peername")
    print(f"Cliente conectado: {endereco}")
    sessao = None
    try:
        while True:
            dados = await ler_quadro(leitor)
            if dados is None:
                break
            mensagem = decodificar_mensagem(dados)
            tipo = mensagem["type"]
            if tipo == "REGISTER" and sessao is None:
                id_cliente = validar_id_cliente(mensagem.get("client_id"))
                decodificar_chave_publica(mensagem.get("client_public_key"))
                participantes = sessoes.listar_clientes()
                sessao = sessoes.registrar_cliente(
                    id_cliente, mensagem["client_public_key"], escritor
                )
                await enviar(sessao, {
                    "type": "CLIENT_LIST",
                    "clients": [
                        {"client_id": participante.id_cliente, "client_public_key": participante.chave_publica}
                        for participante in participantes
                    ],
                })
                for participante in participantes:
                    try:
                        await enviar(participante, {
                            "type": "CLIENT_JOINED",
                            "client_id": sessao.id_cliente,
                            "client_public_key": sessao.chave_publica,
                        })
                    except (ConnectionError, OSError):
                        pass
            elif tipo == "RELAY" and sessao is not None:
                await encaminhar(mensagem, sessao, sessoes, enviar)
            else:
                raise ErroProtocolo("unexpected message type or state")
    except (ErroQuadro, ErroProtocolo, ValueError) as erro:
        print(f"Erro de protocolo de {endereco}: {erro}")
    except (ConnectionError, OSError, asyncio.IncompleteReadError) as erro:
        print(f"Conexão encerrada de {endereco}: {type(erro).__name__}")
    finally:
        if sessao is not None and sessoes.remover_cliente(sessao.id_cliente, escritor):
            for participante in sessoes.listar_clientes():
                try:
                    await enviar(participante, {"type": "CLIENT_LEFT", "client_id": sessao.id_cliente})
                except (ConnectionError, OSError):
                    pass
        print(f"Cliente desconectado: {endereco}")
        escritor.close()
        try:
            await escritor.wait_closed()
        except (ConnectionError, OSError):
            pass
