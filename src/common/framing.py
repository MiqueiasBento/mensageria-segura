"""Quadros TCP com prefixo de comprimento para cliente e servidor."""

import asyncio

TAMANHO_MAXIMO_QUADRO = 64 * 1024


class ErroQuadro(ValueError):
    pass


async def ler_quadro(leitor):
    try:
        cabecalho = await leitor.readexactly(4)
    except asyncio.IncompleteReadError as erro:
        if not erro.partial:
            return None
        raise ErroQuadro("incomplete frame header") from erro
    tamanho = int.from_bytes(cabecalho, "big")
    if not 0 < tamanho <= TAMANHO_MAXIMO_QUADRO:
        raise ErroQuadro("invalid frame length")
    try:
        return await leitor.readexactly(tamanho)
    except asyncio.IncompleteReadError as erro:
        raise ErroQuadro("incomplete frame body") from erro


async def escrever_quadro(escritor, dados):
    if not isinstance(dados, bytes) or not 0 < len(dados) <= TAMANHO_MAXIMO_QUADRO:
        raise ErroQuadro("invalid frame body")
    escritor.write(len(dados).to_bytes(4, "big") + dados)
    await escritor.drain()
