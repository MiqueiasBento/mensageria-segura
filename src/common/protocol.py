"""Mensagens JSON de controle para a etapa inicial sem criptografia."""

import base64
import binascii
import json
from uuid import UUID


class ErroProtocolo(ValueError):
    pass


def codificar_mensagem(mensagem):
    return json.dumps(mensagem, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def decodificar_mensagem(dados):
    try:
        mensagem = json.loads(dados.decode("utf-8"))
    except (UnicodeError, ValueError) as erro:
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
    if len(chave) != 32 or base64.b64encode(chave).decode("ascii") != valor:
        raise ErroProtocolo("client_public_key must contain 32 bytes")
    return chave


def decodificar_conteudo(valor):
    if not isinstance(valor, str):
        raise ErroProtocolo("invalid payload")
    try:
        conteudo = base64.b64decode(valor, validate=True)
    except (ValueError, binascii.Error) as erro:
        raise ErroProtocolo("invalid payload") from erro
    if not conteudo or len(conteudo) > 8192:
        raise ErroProtocolo("payload length must be 1..8192 bytes")
    return conteudo
