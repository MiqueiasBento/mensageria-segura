import os
import uuid

import pytest
from cryptography.exceptions import InvalidTag

from src.common.constants import (
    MAX_TEXTO_CLARO,
    TAMANHO_CABECALHO_E2E,
    TAMANHO_MAXIMO_QUADRO_E2E,
    TAMANHO_MINIMO_QUADRO_E2E,
    TAMANHO_TAG,
)
from src.crypto.aead import (
    MAX_SEQ,
    cifrar,
    decifrar,
    montar_aad,
    montar_nonce,
    montar_quadro_e2e,
    separar_quadro_e2e,
)

CHAVE = bytes(range(16))
IV_BASE = b"\xaa\xbb\xcc\xdd"
ID_A = uuid.UUID("11111111-1111-4111-8111-111111111111").bytes
ID_B = uuid.UUID("22222222-2222-4222-8222-222222222222").bytes


def mensagem_cifrada(texto=b"ola, B", seq=0):
    nonce = montar_nonce(IV_BASE, seq)
    aad = montar_aad(ID_A, ID_B, seq)
    return nonce, aad, cifrar(CHAVE, nonce, texto, aad)


# --- nonce e AAD ------------------------------------------------------------


def testar_nonce_e_iv_base_seguido_do_seq_big_endian():
    assert montar_nonce(IV_BASE, 1) == IV_BASE + b"\x00" * 7 + b"\x01"
    assert montar_nonce(IV_BASE, MAX_SEQ) == IV_BASE + b"\xff" * 8


def testar_seq_diferente_gera_nonce_diferente():
    assert montar_nonce(IV_BASE, 0) != montar_nonce(IV_BASE, 1)


def testar_aad_e_remetente_destinatario_e_seq():
    assert montar_aad(ID_A, ID_B, 5) == ID_A + ID_B + (5).to_bytes(8, "big")


@pytest.mark.parametrize("seq", [-1, MAX_SEQ + 1, 1.0, True], ids=["negativo", "65_bits", "float", "bool"])
def testar_seq_invalido_e_rejeitado(seq):
    with pytest.raises(ValueError):
        montar_nonce(IV_BASE, seq)
    with pytest.raises(ValueError):
        montar_aad(ID_A, ID_B, seq)


def testar_iv_base_e_ids_com_tamanho_errado_sao_rejeitados():
    with pytest.raises(ValueError):
        montar_nonce(b"\x00" * 3, 0)
    with pytest.raises(ValueError):
        montar_aad(ID_A[:15], ID_B, 0)


# --- cifrar / decifrar ------------------------------------------------------


def testar_ida_e_volta_devolve_o_texto():
    nonce, aad, cifrado = mensagem_cifrada(b"ola, B")
    assert decifrar(CHAVE, nonce, cifrado, aad) == b"ola, B"


def testar_cifrado_tem_tag_de_16_bytes_e_esconde_o_texto():
    texto = b"segredo da conversa"
    _, _, cifrado = mensagem_cifrada(texto)
    assert len(cifrado) == len(texto) + TAMANHO_TAG
    assert texto not in cifrado


def testar_texto_de_4096_bytes_e_aceito():
    texto = os.urandom(MAX_TEXTO_CLARO)
    nonce, aad, cifrado = mensagem_cifrada(texto)
    assert decifrar(CHAVE, nonce, cifrado, aad) == texto


def testar_texto_de_4097_bytes_e_rejeitado():
    with pytest.raises(ValueError):
        mensagem_cifrada(b"x" * (MAX_TEXTO_CLARO + 1))


def testar_aad_diferente_falha_a_tag():
    nonce, _, cifrado = mensagem_cifrada(seq=0)
    with pytest.raises(InvalidTag):
        decifrar(CHAVE, nonce, cifrado, montar_aad(ID_A, ID_B, 1))
    with pytest.raises(InvalidTag):
        decifrar(CHAVE, nonce, cifrado, montar_aad(ID_B, ID_A, 0))


def testar_chave_errada_falha_a_tag():
    nonce, aad, cifrado = mensagem_cifrada()
    with pytest.raises(InvalidTag):
        decifrar(bytes(16), nonce, cifrado, aad)


def testar_nonce_errado_falha_a_tag():
    _, aad, cifrado = mensagem_cifrada(seq=0)
    with pytest.raises(InvalidTag):
        decifrar(CHAVE, montar_nonce(IV_BASE, 1), cifrado, aad)


def testar_bit_invertido_no_cifrado_falha_a_tag():
    nonce, aad, cifrado = mensagem_cifrada()
    for posicao in (0, len(cifrado) - 1):  # primeiro byte do texto e ultimo byte da tag
        adulterado = bytearray(cifrado)
        adulterado[posicao] ^= 0x01
        with pytest.raises(InvalidTag):
            decifrar(CHAVE, nonce, bytes(adulterado), aad)


def testar_chave_aes_256_e_rejeitada():
    # O trabalho exige AES-128: uma chave de 32 bytes indica erro na derivacao.
    with pytest.raises(ValueError):
        cifrar(bytes(32), montar_nonce(IV_BASE, 0), b"x", b"")


def testar_cifrado_menor_que_a_tag_e_rejeitado():
    with pytest.raises(ValueError):
        decifrar(CHAVE, montar_nonce(IV_BASE, 0), b"\x00" * (TAMANHO_TAG - 1), b"")


# --- quadro E2E --------------------------------------------------------------


def testar_quadro_tem_os_campos_na_ordem_do_enunciado():
    nonce, _, cifrado = mensagem_cifrada(seq=7)
    quadro = montar_quadro_e2e(nonce, ID_A, ID_B, 7, cifrado)
    assert quadro[:12] == nonce
    assert quadro[12:28] == ID_A
    assert quadro[28:44] == ID_B
    assert quadro[44:52] == (7).to_bytes(8, "big")
    assert quadro[TAMANHO_CABECALHO_E2E:] == cifrado


def testar_montar_e_separar_quadro_devolvem_os_mesmos_campos():
    nonce, aad, cifrado = mensagem_cifrada(b"ida e volta", seq=42)
    quadro = montar_quadro_e2e(nonce, ID_A, ID_B, 42, cifrado)
    assert separar_quadro_e2e(quadro) == (nonce, ID_A, ID_B, 42, cifrado)


def testar_fluxo_completo_do_remetente_ao_destinatario():
    seq = 3
    nonce = montar_nonce(IV_BASE, seq)
    cifrado = cifrar(CHAVE, nonce, b"mensagem E2E", montar_aad(ID_A, ID_B, seq))
    quadro = montar_quadro_e2e(nonce, ID_A, ID_B, seq, cifrado)

    # O destinatario reconstroi o AAD a partir do proprio quadro.
    nonce_r, remetente, destinatario, seq_r, cifrado_r = separar_quadro_e2e(quadro)
    aad = montar_aad(remetente, destinatario, seq_r)
    assert decifrar(CHAVE, nonce_r, cifrado_r, aad) == b"mensagem E2E"


def testar_trocar_destinatario_no_quadro_falha_a_tag():
    nonce, _, cifrado = mensagem_cifrada()
    quadro = bytearray(montar_quadro_e2e(nonce, ID_A, ID_B, 0, cifrado))
    quadro[28:44] = ID_A  # atacante redireciona o quadro
    nonce_r, remetente, destinatario, seq_r, cifrado_r = separar_quadro_e2e(bytes(quadro))
    with pytest.raises(InvalidTag):
        decifrar(CHAVE, nonce_r, cifrado_r, montar_aad(remetente, destinatario, seq_r))


def testar_quadro_minimo_e_maximo_sao_aceitos():
    for texto in (b"", b"x" * MAX_TEXTO_CLARO):
        nonce, _, cifrado = mensagem_cifrada(texto)
        quadro = montar_quadro_e2e(nonce, ID_A, ID_B, 0, cifrado)
        assert len(quadro) in (TAMANHO_MINIMO_QUADRO_E2E, TAMANHO_MAXIMO_QUADRO_E2E)
        assert separar_quadro_e2e(quadro)[4] == cifrado


@pytest.mark.parametrize(
    "tamanho",
    [0, TAMANHO_CABECALHO_E2E, TAMANHO_MINIMO_QUADRO_E2E - 1, TAMANHO_MAXIMO_QUADRO_E2E + 1],
    ids=["vazio", "so_cabecalho", "sem_tag_completa", "acima_do_maximo"],
)
def testar_quadro_com_tamanho_invalido_e_rejeitado(tamanho):
    with pytest.raises(ValueError):
        separar_quadro_e2e(b"\x00" * tamanho)


def testar_montar_quadro_rejeita_cifrado_sem_tag():
    with pytest.raises(ValueError):
        montar_quadro_e2e(montar_nonce(IV_BASE, 0), ID_A, ID_B, 0, b"\x00" * (TAMANHO_TAG - 1))
