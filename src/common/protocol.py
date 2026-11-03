"""Serialização e validação dos campos públicos do protocolo."""

import base64
import binascii
import json
from uuid import UUID

from src.common.constants import TAMANHO_MAXIMO_QUADRO_E2E, TAMANHO_CHAVE_PUBLICA


class ErroProtocolo(ValueError):
    pass


def codificar_mensagem(mensagem):
    return json.dumps(mensagem, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def decodificar_mensagem(dados):
    try:
        mensagem = json.loads(dados.decode("utf-8"), object_pairs_hook=_objeto_sem_repeticao, parse_constant=_constante_invalida)
    except (UnicodeError, ValueError, RecursionError) as erro:
        raise ErroProtocolo("invalid JSON message") from erro
    if not isinstance(mensagem, dict) or not isinstance(mensagem.get("type"), str):
        raise ErroProtocolo("message must have a type")
    return mensagem


def validar_id_cliente(valor):
    try:
        identificador = UUID(valor)
    except (ValueError, TypeError, AttributeError) as erro:
        raise ErroProtocolo("invalid client_id") from erro
    if identificador.version != 4 or str(identificador) != valor:
        raise ErroProtocolo("client_id must be canonical UUIDv4")
    return valor


def decodificar_chave_publica(valor):
    if not isinstance(valor, str):
        raise ErroProtocolo("invalid client_public_key")
    try:
        chave = base64.b64decode(valor, validate=True)
    except (ValueError, binascii.Error) as erro:
        raise ErroProtocolo("invalid client_public_key") from erro
    if len(chave) != TAMANHO_CHAVE_PUBLICA or base64.b64encode(chave).decode("ascii") != valor:
        raise ErroProtocolo("client_public_key must contain 32 bytes")
    return chave


def decodificar_conteudo(valor):
    if not isinstance(valor, str):
        raise ErroProtocolo("invalid payload")
    try:
        conteudo = base64.b64decode(valor, validate=True)
    except (ValueError, binascii.Error) as erro:
        raise ErroProtocolo("invalid payload") from erro
    if not conteudo or len(conteudo) > TAMANHO_MAXIMO_QUADRO_E2E:
        raise ErroProtocolo("payload length must be 1..4164 bytes")
    return conteudo


def _objeto_sem_repeticao(pares):
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ErroProtocolo("campo JSON repetido")
        objeto[chave] = valor
    return objeto


def _constante_invalida(valor):
    raise ErroProtocolo("constante JSON não permitida")
