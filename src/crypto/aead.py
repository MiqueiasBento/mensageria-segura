"""AES-128-GCM e o quadro E2E binario trocado entre clientes.

quadro = nonce(12) | sender_id(16) | recipient_id(16) | seq_no(8) | ciphertext+tag
nonce  = IV_base(4) || seq_no(8, big-endian)
AAD    = sender_id || recipient_id || seq_no
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.common.constants import (
    MAX_TEXTO_CLARO,
    TAMANHO_CABECALHO_E2E,
    TAMANHO_CHAVE_AES,
    TAMANHO_ID,
    TAMANHO_IV_BASE,
    TAMANHO_MAXIMO_QUADRO_E2E,
    TAMANHO_MINIMO_QUADRO_E2E,
    TAMANHO_NONCE,
    TAMANHO_SEQ,
    TAMANHO_TAG,
)

MAX_SEQ = 2 ** (8 * TAMANHO_SEQ) - 1


def _exigir_bytes(valor, tamanho, nome):
    if not isinstance(valor, bytes) or len(valor) != tamanho:
        raise ValueError(f"{nome} must contain {tamanho} bytes")


def _seq_em_bytes(seq):
    if not isinstance(seq, int) or isinstance(seq, bool) or not 0 <= seq <= MAX_SEQ:
        raise ValueError("seq_no must be an unsigned 64-bit integer")
    return seq.to_bytes(TAMANHO_SEQ, "big")


def montar_nonce(iv_base, seq):
    _exigir_bytes(iv_base, TAMANHO_IV_BASE, "IV_base")
    return iv_base + _seq_em_bytes(seq)


def montar_aad(id_remetente, id_destinatario, seq):
    _exigir_bytes(id_remetente, TAMANHO_ID, "sender_id")
    _exigir_bytes(id_destinatario, TAMANHO_ID, "recipient_id")
    return id_remetente + id_destinatario + _seq_em_bytes(seq)


def cifrar(chave, nonce, texto_claro, aad):
    """Retorna ciphertext || tag (a tag de 16 bytes fica no final)."""
    _exigir_bytes(chave, TAMANHO_CHAVE_AES, "key")
    _exigir_bytes(nonce, TAMANHO_NONCE, "nonce")
    if not isinstance(texto_claro, bytes) or len(texto_claro) > MAX_TEXTO_CLARO:
        raise ValueError("plaintext must be bytes with at most 4096 bytes")
    return AESGCM(chave).encrypt(nonce, texto_claro, aad)


def decifrar(chave, nonce, cifrado, aad):
    """Retorna o texto claro; lanca cryptography.exceptions.InvalidTag se algo foi alterado."""
    _exigir_bytes(chave, TAMANHO_CHAVE_AES, "key")
    _exigir_bytes(nonce, TAMANHO_NONCE, "nonce")
    if not isinstance(cifrado, bytes) or not TAMANHO_TAG <= len(cifrado) <= MAX_TEXTO_CLARO + TAMANHO_TAG:
        raise ValueError("invalid ciphertext length")
    return AESGCM(chave).decrypt(nonce, cifrado, aad)


def montar_quadro_e2e(nonce, id_remetente, id_destinatario, seq, cifrado):
    _exigir_bytes(nonce, TAMANHO_NONCE, "nonce")
    if not isinstance(cifrado, bytes) or not TAMANHO_TAG <= len(cifrado) <= MAX_TEXTO_CLARO + TAMANHO_TAG:
        raise ValueError("invalid ciphertext length")
    return nonce + montar_aad(id_remetente, id_destinatario, seq) + cifrado


def separar_quadro_e2e(quadro):
    """Retorna (nonce, id_remetente, id_destinatario, seq, cifrado)."""
    if not isinstance(quadro, bytes) or not TAMANHO_MINIMO_QUADRO_E2E <= len(quadro) <= TAMANHO_MAXIMO_QUADRO_E2E:
        raise ValueError("invalid E2E frame length")
    inicio_ids = TAMANHO_NONCE
    inicio_seq = inicio_ids + 2 * TAMANHO_ID
    nonce = quadro[:inicio_ids]
    id_remetente = quadro[inicio_ids:inicio_ids + TAMANHO_ID]
    id_destinatario = quadro[inicio_ids + TAMANHO_ID:inicio_seq]
    seq = int.from_bytes(quadro[inicio_seq:TAMANHO_CABECALHO_E2E], "big")
    cifrado = quadro[TAMANHO_CABECALHO_E2E:]
    return nonce, id_remetente, id_destinatario, seq, cifrado
