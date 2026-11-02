"""Chaves efemeras X25519 e segredo compartilhado ECDH entre dois clientes."""

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.common.constants import TAMANHO_CHAVE_PUBLICA


def gerar_par_efemero():
    """Retorna (chave_privada: X25519PrivateKey, chave_publica: bytes de 32)."""
    chave_privada = X25519PrivateKey.generate()
    chave_publica = chave_privada.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return chave_privada, chave_publica


def calcular_segredo(chave_privada, chave_publica_peer):
    """Retorna Z = ECDH(sk_eu, pk_peer), com 32 bytes."""
    if not isinstance(chave_publica_peer, bytes) or len(chave_publica_peer) != TAMANHO_CHAVE_PUBLICA:
        raise ValueError("peer public key must contain 32 bytes")
    # exchange() lanca ValueError se a chave do peer for de ordem baixa (Z so com zeros).
    return chave_privada.exchange(X25519PublicKey.from_public_bytes(chave_publica_peer))
