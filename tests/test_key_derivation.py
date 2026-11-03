import uuid

import pytest

from src.common.constants import TAMANHO_CHAVE_AES, TAMANHO_CHAVE_PUBLICA
from src.crypto.key_derivation import (
    SALT_PROVISORIO,
    calcular_segredo,
    derivar_chaves,
    gerar_par_efemero,
    hkdf_expand,
    hkdf_extract,
)


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


# --- Etapa 4: HKDF ---------------------------------------------------------


def novo_id():
    return uuid.uuid4().bytes


def par_com_segredo():
    """Dois clientes com ids e o Z que ambos calculam."""
    privada_a, publica_a = gerar_par_efemero()
    privada_b, publica_b = gerar_par_efemero()
    segredo = calcular_segredo(privada_a, publica_b)
    assert segredo == calcular_segredo(privada_b, publica_a)
    return segredo, novo_id(), novo_id()


def testar_vetor_rfc5869_caso_1():
    ikm = bytes.fromhex("0b" * 22)
    salt = bytes.fromhex("000102030405060708090a0b0c")
    info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
    prk = hkdf_extract(salt, ikm)
    assert prk.hex() == "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5"
    assert hkdf_expand(prk, info, 42).hex() == (
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
    )


def testar_envio_de_um_lado_e_recebimento_do_outro():
    segredo, id_a, id_b = par_com_segredo()
    envio_a, recebimento_a = derivar_chaves(segredo, SALT_PROVISORIO, id_a, id_b)
    envio_b, recebimento_b = derivar_chaves(segredo, SALT_PROVISORIO, id_b, id_a)
    assert envio_a == recebimento_b
    assert envio_b == recebimento_a


def testar_direcoes_usam_chaves_diferentes():
    segredo, id_a, id_b = par_com_segredo()
    envio, recebimento = derivar_chaves(segredo, SALT_PROVISORIO, id_a, id_b)
    assert envio != recebimento


def testar_chaves_tem_16_bytes():
    segredo, id_a, id_b = par_com_segredo()
    for chave in derivar_chaves(segredo, SALT_PROVISORIO, id_a, id_b):
        assert len(chave) == TAMANHO_CHAVE_AES


def testar_menor_id_e_o_lado_a():
    segredo, _, _ = par_com_segredo()
    id_menor, id_maior = bytes(15) + b"\x01", bytes(15) + b"\x02"
    prk = hkdf_extract(SALT_PROVISORIO, segredo)
    a2b, b2a = hkdf_expand(prk, b"A2B"), hkdf_expand(prk, b"B2A")
    assert derivar_chaves(segredo, SALT_PROVISORIO, id_menor, id_maior) == (a2b, b2a)
    assert derivar_chaves(segredo, SALT_PROVISORIO, id_maior, id_menor) == (b2a, a2b)


def testar_salt_diferente_gera_chaves_diferentes():
    segredo, id_a, id_b = par_com_segredo()
    com_salt_zero = derivar_chaves(segredo, SALT_PROVISORIO, id_a, id_b)
    com_outro_salt = derivar_chaves(segredo, b"\x01" * 16, id_a, id_b)
    assert set(com_salt_zero).isdisjoint(com_outro_salt)


def testar_salts_diferentes_nos_dois_lados_nao_combinam():
    segredo, id_a, id_b = par_com_segredo()
    envio_a, _ = derivar_chaves(segredo, SALT_PROVISORIO, id_a, id_b)
    _, recebimento_b = derivar_chaves(segredo, b"\x01" * 16, id_b, id_a)
    assert envio_a != recebimento_b


def testar_pares_diferentes_tem_chaves_diferentes():
    segredo_1, id_a, id_b = par_com_segredo()
    segredo_2, _, _ = par_com_segredo()
    assert derivar_chaves(segredo_1, SALT_PROVISORIO, id_a, id_b) != derivar_chaves(
        segredo_2, SALT_PROVISORIO, id_a, id_b
    )


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("segredo", b"\x01" * 31),
        ("salt", b"\x01" * 15),
        ("meu_id", b"\x01" * 15),
        ("id_peer", "texto-nao-bytes!"),
    ],
    ids=["segredo_31_bytes", "salt_15_bytes", "meu_id_15_bytes", "id_peer_str"],
)
def testar_entradas_com_tamanho_invalido_sao_rejeitadas(campo, valor):
    segredo, id_a, id_b = par_com_segredo()
    argumentos = {"segredo": segredo, "salt": SALT_PROVISORIO, "meu_id": id_a, "id_peer": id_b}
    argumentos[campo] = valor
    with pytest.raises(ValueError):
        derivar_chaves(**argumentos)


def testar_id_do_peer_igual_ao_proprio_e_rejeitado():
    segredo, id_a, _ = par_com_segredo()
    with pytest.raises(ValueError):
        derivar_chaves(segredo, SALT_PROVISORIO, id_a, id_a)
