"""Run with: python -m src.server.main"""

import asyncio
from functools import partial

from src.server.connection import atender_cliente
from src.server.sessions import RegistroSessoes

ENDERECO = "127.0.0.1"
PORTA = 8000


async def iniciar_servidor(endereco_servidor=ENDERECO, porta=PORTA, sessoes=None):
    registro = sessoes if sessoes is not None else RegistroSessoes()
    return await asyncio.start_server(partial(atender_cliente, sessoes=registro), endereco_servidor, porta)


async def principal():
    servidor = await iniciar_servidor()
    print(f"Servidor iniciado em {ENDERECO}:{PORTA}")
    async with servidor:
        await servidor.serve_forever()


if __name__ == "__main__":
    asyncio.run(principal())
