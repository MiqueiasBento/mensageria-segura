"""RSA-PSS autentica X25519; HMAC protege o controle em cada conexão."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.common.protocol import ErroProtocolo, validar_id_cliente
from src.crypto.identity import ErroIdentidade, validar_certificado
from src.crypto.key_derivation import calcular_segredo, gerar_par_efemero

VERSAO = 1
MAX_SEQUENCIA = 2**64 - 1


class ErroHandshake(ErroProtocolo):
    pass


def para_base64(dados):
    return base64.b64encode(dados).decode("ascii")


def de_base64(valor, tamanho=None):
    try:
        if not isinstance(valor, str):
            raise ValueError()
        dados = base64.b64decode(valor, validate=True)
        if para_base64(dados) != valor or (tamanho is not None and len(dados) != tamanho):
            raise ValueError()
        return dados
    except (ValueError, TypeError) as erro:
        raise ErroHandshake("campo binário inválido") from erro


def transcricao(chave_servidor, chave_cliente, id_cliente, salt):
    validar_id_cliente(id_cliente)
    for dados, tamanho in ((chave_servidor, 32), (chave_cliente, 32), (salt, 16)):
        if not isinstance(dados, bytes) or len(dados) != tamanho:
            raise ErroHandshake("tamanho inválido na transcrição")
    return chave_servidor + chave_cliente + UUID(id_cliente).bytes + salt


def _canonico(mensagem):
    try:
        return json.dumps(mensagem, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    except (ValueError, TypeError, RecursionError) as erro:
        raise ErroHandshake("mensagem não possui representação canônica válida") from erro


@dataclass
class CanalAutenticado:
    id_sessao: str
    chave_envio: bytes = field(repr=False)
    chave_recebimento: bytes = field(repr=False)
    seq_envio: int = 0
    seq_recebimento: int = 0  # Próximo valor esperado; TCP preserva a ordem.

    def empacotar(self, mensagem):
        if self.seq_envio > MAX_SEQUENCIA:
            raise ErroHandshake("contador administrativo esgotado")
        envelope = {"type": "AUTH", "session_id": self.id_sessao,
                    "seq_no": self.seq_envio, "message": mensagem}
        envelope["mac"] = para_base64(hmac.digest(self.chave_envio, _canonico(envelope), "sha256"))
        self.seq_envio += 1
        return envelope

    def desempacotar(self, envelope):
        if not isinstance(envelope, dict) or set(envelope) != {"type", "session_id", "seq_no", "message", "mac"}:
            raise ErroHandshake("envelope administrativo inválido")
        seq = envelope["seq_no"]
        if envelope["type"] != "AUTH" or envelope["session_id"] != self.id_sessao:
            raise ErroHandshake("sessão administrativa incorreta")
        if type(seq) is not int or not 0 <= seq <= MAX_SEQUENCIA or seq != self.seq_recebimento:
            raise ErroHandshake("sequência administrativa inválida ou repetida")
        mensagem = envelope["message"]
        if not isinstance(mensagem, dict) or not isinstance(mensagem.get("type"), str):
            raise ErroHandshake("mensagem administrativa inválida")
        autenticado = {campo: valor for campo, valor in envelope.items() if campo != "mac"}
        esperado = hmac.digest(self.chave_recebimento, _canonico(autenticado), "sha256")
        if not hmac.compare_digest(esperado, de_base64(envelope["mac"], 32)):
            raise ErroHandshake("autenticação administrativa inválida")
        self.seq_recebimento += 1
        return mensagem


def _criar_canal(segredo, salt, dados, lado_servidor):
    resumo = hashlib.sha256(dados).digest()
    material = HKDF(algorithm=hashes.SHA256(), length=64, salt=salt,
                    info=b"mensageria-v1/controle/" + resumo).derive(segredo)
    envio_cliente, envio_servidor = material[:32], material[32:]
    if lado_servidor:
        return CanalAutenticado(resumo.hex(), envio_servidor, envio_cliente)
    return CanalAutenticado(resumo.hex(), envio_cliente, envio_servidor)


def criar_handshake(identidade, chave_cliente, id_cliente, salt):
    privada, publica = gerar_par_efemero()
    dados = transcricao(publica, chave_cliente, id_cliente, salt)
    try:
        segredo = calcular_segredo(privada, chave_cliente)
    except ValueError as erro:
        raise ErroHandshake("chave efêmera do cliente inválida") from erro
    assinatura = identidade.chave_privada.sign(
        hashlib.sha256(dados).digest(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
        utils.Prehashed(hashes.SHA256()),
    )
    mensagem = {"type": "HANDSHAKE", "version": VERSAO,
                "server_public_key": para_base64(publica),
                "certificate": para_base64(identidade.certificado),
                "signature": para_base64(assinatura), "salt": para_base64(salt)}
    return mensagem, _criar_canal(segredo, salt, dados, True)


def validar_handshake(mensagem, certificado_confiavel, chave_privada, chave_publica, id_cliente):
    if not isinstance(mensagem, dict) or set(mensagem) != {"type", "version", "server_public_key", "certificate", "signature", "salt"}:
        raise ErroHandshake("resposta de handshake inválida")
    if mensagem["type"] != "HANDSHAKE" or type(mensagem["version"]) is not int or mensagem["version"] != VERSAO:
        raise ErroHandshake("versão de handshake não aceita")
    try:
        confiavel = validar_certificado(certificado_confiavel)
        recebido = validar_certificado(de_base64(mensagem["certificate"]))
        if recebido.public_bytes(serialization.Encoding.DER) != confiavel.public_bytes(serialization.Encoding.DER):
            raise ErroHandshake("certificado não corresponde ao certificado provisionado")
        publica = de_base64(mensagem["server_public_key"], 32)
        salt = de_base64(mensagem["salt"], 16)
        dados = transcricao(publica, chave_publica, id_cliente, salt)
        confiavel.public_key().verify(
            de_base64(mensagem["signature"]), hashlib.sha256(dados).digest(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
            utils.Prehashed(hashes.SHA256()),
        )
        segredo = calcular_segredo(chave_privada, publica)
    except (ErroIdentidade, InvalidSignature, ValueError) as erro:
        raise ErroHandshake("certificado, assinatura ou chave efêmera inválidos") from erro
    return salt, _criar_canal(segredo, salt, dados, False)
