import pytest

from src.common.constants import TAMANHO_CHAVE_PUBLICA
from src.crypto.key_derivation import calcular_segredo, gerar_par_efemero


def testar_chave_publica_tem_32_bytes():
    _, chave_publica = gerar_par_efemero()
    assert isinstance(chave_publica, bytes)
    assert len(chave_publica) == TAMANHO_CHAVE_PUBLICA


def testar_cada_par_gerado_e_diferente():
    _, publica_1 = gerar_par_efemero()
    _, publica_2 = gerar_par_efemero()
    assert publica_1 != publica_2


def testar_a_e_b_calculam_o_mesmo_segredo():
    privada_a, publica_a = gerar_par_efemero()
    privada_b, publica_b = gerar_par_efemero()
    segredo_a = calcular_segredo(privada_a, publica_b)
    segredo_b = calcular_segredo(privada_b, publica_a)
    assert segredo_a == segredo_b
    assert len(segredo_a) == 32


def testar_terceiro_cliente_obtem_segredo_diferente():
    privada_a, _ = gerar_par_efemero()
    _, publica_b = gerar_par_efemero()
    _, publica_c = gerar_par_efemero()
    assert calcular_segredo(privada_a, publica_b) != calcular_segredo(privada_a, publica_c)


def testar_segredo_nao_depende_so_das_chaves_publicas():
    # O servidor ve as duas chaves publicas, mas sem uma privada nao chega em Z.
    privada_a, publica_a = gerar_par_efemero()
    _, publica_b = gerar_par_efemero()
    privada_intrusa, _ = gerar_par_efemero()
    assert calcular_segredo(privada_intrusa, publica_b) != calcular_segredo(privada_a, publica_b)


@pytest.mark.parametrize(
    "chave",
    [b"\x01" * 31, b"\x01" * 33, b"", "x" * 32],
    ids=["31_bytes", "33_bytes", "vazia", "str"],
)
def testar_chave_publica_com_formato_invalido_e_rejeitada(chave):
    privada, _ = gerar_par_efemero()
    with pytest.raises(ValueError):
        calcular_segredo(privada, chave)


def testar_chave_publica_de_ordem_baixa_e_rejeitada():
    # Um ponto de ordem baixa forca Z = 0, que um atacante conheceria.
    privada, _ = gerar_par_efemero()
    with pytest.raises(ValueError):
        calcular_segredo(privada, bytes(32))
