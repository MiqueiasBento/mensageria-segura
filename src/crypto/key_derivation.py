"""Chaves efemeras X25519, segredo ECDH e derivacao HKDF das chaves direcionais."""

from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.common.constants import TAMANHO_CHAVE_AES, TAMANHO_CHAVE_PUBLICA, TAMANHO_ID, TAMANHO_SALT

# Remover na Etapa 10, quando o salt_srv chegar pelo handshake do servidor.
SALT_PROVISORIO = bytes(TAMANHO_SALT)
TAMANHO_SEGREDO = 32  # saida do X25519


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


def hkdf_extract(salt, segredo):
    """PRK = HMAC-SHA256(salt, Z), com 32 bytes."""
    h = hmac.HMAC(salt, hashes.SHA256())
    h.update(segredo)
    return h.finalize()


def hkdf_expand(prk, rotulo, tamanho=TAMANHO_CHAVE_AES):
    """Deriva `tamanho` bytes do PRK, separados pelo rotulo (info)."""
    return HKDFExpand(hashes.SHA256(), tamanho, rotulo).derive(prk)


def derivar_chaves(segredo, salt, meu_id, id_peer):
    """Retorna (chave_envio, chave_recebimento). IDs em 16 bytes (uuid.UUID(texto).bytes).

    O cliente de menor id em bytes e o "A" do par; assim os dois lados
    concordam sobre qual chave e A2B e qual e B2A sem trocar mensagens.
    """
    if not isinstance(segredo, bytes) or len(segredo) != TAMANHO_SEGREDO:
        raise ValueError("shared secret must contain 32 bytes")
    if not isinstance(salt, bytes) or len(salt) != TAMANHO_SALT:
        raise ValueError("salt must contain 16 bytes")
    for identificador in (meu_id, id_peer):
        if not isinstance(identificador, bytes) or len(identificador) != TAMANHO_ID:
            raise ValueError("client ids must contain 16 bytes")
    if meu_id == id_peer:
        raise ValueError("peer id must differ from own id")

    prk = hkdf_extract(salt, segredo)
    chave_a2b = hkdf_expand(prk, b"A2B")
    chave_b2a = hkdf_expand(prk, b"B2A")
    if meu_id < id_peer:
        return chave_a2b, chave_b2a
    return chave_b2a, chave_a2b
