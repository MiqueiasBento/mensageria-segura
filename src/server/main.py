"""Execute com: python -m src.server.main."""

import argparse
import asyncio
import os
from functools import partial

from src.crypto.identity import CAMINHO_CERTIFICADO, CAMINHO_CHAVE, carregar_identidade
from src.server.connection import atender_cliente
from src.server.sessions import RegistroSessoes

ENDERECO = "127.0.0.1"
PORTA = 8000


async def iniciar_servidor(endereco_servidor=ENDERECO, porta=PORTA, sessoes=None, identidade=None):
    registro = sessoes if sessoes is not None else RegistroSessoes()
    identidade = identidade if identidade is not None else carregar_identidade()
    salt = os.urandom(16)  # Comum aos pares desta execução; nunca é constante no código.
    return await asyncio.start_server(
        partial(atender_cliente, sessoes=registro, identidade=identidade, salt=salt), endereco_servidor, porta
    )


async def principal(endereco=ENDERECO, porta=PORTA, identidade=None):
    servidor = await iniciar_servidor(endereco, porta, identidade=identidade)
    print(f"Servidor iniciado em {endereco}:{servidor.sockets[0].getsockname()[1]}")
    async with servidor:
        await servidor.serve_forever()


def executar():
    argumentos = argparse.ArgumentParser(description="Servidor de mensageria segura")
    argumentos.add_argument("--host", default=ENDERECO)
    argumentos.add_argument("--port", type=int, default=PORTA)
    argumentos.add_argument("--chave", default=str(CAMINHO_CHAVE))
    argumentos.add_argument("--certificado", default=str(CAMINHO_CERTIFICADO))
    opcoes = argumentos.parse_args()
    try:
        identidade = carregar_identidade(opcoes.chave, opcoes.certificado)
        asyncio.run(principal(opcoes.host, opcoes.port, identidade))
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError) as erro:
        argumentos.exit(1, f"Falha ao iniciar: {erro}. Gere/provisione a identidade antes de iniciar.\n")


if __name__ == "__main__":
    executar()
