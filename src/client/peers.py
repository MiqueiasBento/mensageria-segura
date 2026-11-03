"""Estado criptografico por peer: chaves direcionais, contadores e anti-replay."""

import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag

from src.common.constants import TAMANHO_IV_BASE
from src.crypto.aead import (
    MAX_SEQ,
    cifrar,
    decifrar,
    montar_aad,
    montar_nonce,
    montar_quadro_e2e,
    separar_quadro_e2e,
)
from src.crypto.key_derivation import calcular_segredo, derivar_chaves


class ErroReplay(ValueError):
    pass


class ErroMensagem(ValueError):
    """Quadro malformado, ids inesperados, nonce inconsistente ou tag invalida."""


@dataclass
class EstadoPeer:
    id_peer: bytes
    chave_publica: bytes
    # repr=False: um print/log acidental do estado nao expoe material secreto.
    chave_envio: bytes = field(repr=False)
    chave_recebimento: bytes = field(repr=False)
    seq_envio: int = 0
    seq_recebimento: int = -1
    iv_base_envio: bytes = field(default_factory=lambda: os.urandom(TAMANHO_IV_BASE), repr=False)
    iv_base_recebimento: bytes | None = field(default=None, repr=False)  # aprendido no 1o quadro valido


def criar_estado_peer(minha_chave_privada, meu_id, id_peer, chave_publica_peer, salt):
    segredo = calcular_segredo(minha_chave_privada, chave_publica_peer)
    chave_envio, chave_recebimento = derivar_chaves(segredo, salt, meu_id, id_peer)
    return EstadoPeer(id_peer, chave_publica_peer, chave_envio, chave_recebimento)


def preparar_envio(estado, meu_id, texto_claro):
    """Cifra o texto e retorna o quadro E2E; so consome o seq se o quadro for montado."""
    seq = estado.seq_envio
    if seq > MAX_SEQ:
        raise ErroMensagem("send counter exhausted")
    nonce = montar_nonce(estado.iv_base_envio, seq)
    cifrado = cifrar(estado.chave_envio, nonce, texto_claro, montar_aad(meu_id, estado.id_peer, seq))
    quadro = montar_quadro_e2e(nonce, meu_id, estado.id_peer, seq, cifrado)
    estado.seq_envio = seq + 1
    return quadro


def processar_recebimento(estado, meu_id, quadro):
    """Retorna o texto claro ou lanca ErroReplay/ErroMensagem sem alterar o estado."""
    try:
        nonce, id_remetente, id_destinatario, seq, cifrado = separar_quadro_e2e(quadro)
    except ValueError as erro:
        raise ErroMensagem("malformed E2E frame") from erro
    if id_remetente != estado.id_peer:
        raise ErroMensagem("unexpected sender_id")
    if id_destinatario != meu_id:
        raise ErroMensagem("frame addressed to another client")
    if seq <= estado.seq_recebimento:
        raise ErroReplay("seq_no already accepted")

    iv_base, seq_do_nonce = nonce[:TAMANHO_IV_BASE], nonce[TAMANHO_IV_BASE:]
    if seq_do_nonce != seq.to_bytes(len(seq_do_nonce), "big"):
        raise ErroMensagem("nonce does not match seq_no")
    if estado.iv_base_recebimento is not None and iv_base != estado.iv_base_recebimento:
        raise ErroMensagem("unexpected IV_base")

    try:
        texto_claro = decifrar(estado.chave_recebimento, nonce, cifrado, montar_aad(id_remetente, id_destinatario, seq))
    except InvalidTag as erro:
        raise ErroMensagem("authentication failed") from erro

    # Somente apos a tag ser valida: um quadro forjado nao pode avancar o contador.
    estado.seq_recebimento = seq
    if estado.iv_base_recebimento is None:
        estado.iv_base_recebimento = iv_base
    return texto_claro
