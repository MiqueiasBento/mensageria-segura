import asyncio

import pytest

from src.common.framing import TAMANHO_MAXIMO_QUADRO, ErroQuadro, escrever_quadro, ler_quadro


class EscritorFalso:
    """Substitui o StreamWriter guardando os bytes escritos em memoria."""

    def __init__(self):
        self.dados = b""

    def write(self, dados):
        self.dados += dados

    async def drain(self):
        pass


def leitor_com(dados, fechar=True):
    leitor = asyncio.StreamReader()
    leitor.feed_data(dados)
    if fechar:
        leitor.feed_eof()
    return leitor


def quadro(corpo):
    return len(corpo).to_bytes(4, "big") + corpo


@pytest.mark.asyncio
async def testar_escrita_usa_prefixo_big_endian_de_4_bytes():
    escritor = EscritorFalso()
    await escrever_quadro(escritor, b"ola")
    assert escritor.dados == b"\x00\x00\x00\x03ola"


@pytest.mark.asyncio
async def testar_ida_e_volta_preserva_o_corpo():
    escritor = EscritorFalso()
    corpo = bytes(range(256)) * 4
    await escrever_quadro(escritor, corpo)
    assert await ler_quadro(leitor_com(escritor.dados)) == corpo


@pytest.mark.asyncio
async def testar_varios_quadros_no_mesmo_bloco_tcp():
    leitor = leitor_com(quadro(b"primeiro") + quadro(b"segundo") + quadro(b"terceiro"))
    assert await ler_quadro(leitor) == b"primeiro"
    assert await ler_quadro(leitor) == b"segundo"
    assert await ler_quadro(leitor) == b"terceiro"
    assert await ler_quadro(leitor) is None


@pytest.mark.asyncio
async def testar_quadro_entregue_byte_a_byte():
    leitor = asyncio.StreamReader()
    tarefa = asyncio.create_task(ler_quadro(leitor))
    for byte in quadro(b"fragmentado"):
        await asyncio.sleep(0)
        assert not tarefa.done()
        leitor.feed_data(bytes([byte]))
    assert await asyncio.wait_for(tarefa, 1) == b"fragmentado"


@pytest.mark.asyncio
async def testar_eof_sem_dados_retorna_none():
    assert await ler_quadro(leitor_com(b"")) is None


@pytest.mark.asyncio
async def testar_cabecalho_incompleto_e_rejeitado():
    with pytest.raises(ErroQuadro, match="header"):
        await ler_quadro(leitor_com(b"\x00\x00"))


@pytest.mark.asyncio
async def testar_corpo_incompleto_e_rejeitado():
    with pytest.raises(ErroQuadro, match="body"):
        await ler_quadro(leitor_com((10).to_bytes(4, "big") + b"curto"))


@pytest.mark.asyncio
async def testar_tamanho_zero_e_rejeitado():
    with pytest.raises(ErroQuadro, match="length"):
        await ler_quadro(leitor_com((0).to_bytes(4, "big")))


@pytest.mark.asyncio
async def testar_tamanho_acima_do_limite_e_rejeitado_sem_ler_o_corpo():
    # O leitor fica aberto: se o codigo tentasse ler o corpo, o teste travaria.
    leitor = leitor_com((TAMANHO_MAXIMO_QUADRO + 1).to_bytes(4, "big"), fechar=False)
    with pytest.raises(ErroQuadro, match="length"):
        await asyncio.wait_for(ler_quadro(leitor), 1)


@pytest.mark.asyncio
async def testar_tamanho_maximo_e_aceito():
    corpo = b"x" * TAMANHO_MAXIMO_QUADRO
    assert await ler_quadro(leitor_com(quadro(corpo))) == corpo
    escritor = EscritorFalso()
    await escrever_quadro(escritor, corpo)
    assert escritor.dados == quadro(corpo)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dados",
    [b"", b"x" * (TAMANHO_MAXIMO_QUADRO + 1), "texto", bytearray(b"abc")],
    ids=["vazio", "acima_do_limite", "str", "bytearray"],
)
async def testar_escrita_rejeita_corpo_invalido(dados):
    escritor = EscritorFalso()
    with pytest.raises(ErroQuadro):
        await escrever_quadro(escritor, dados)
    assert escritor.dados == b""
