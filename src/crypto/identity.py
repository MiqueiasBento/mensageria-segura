"""Identidade RSA e certificado autoassinado provisionado fora da conexão TCP."""

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

RAIZ = Path(__file__).resolve().parents[2]
CAMINHO_CHAVE = RAIZ / "secrets/server.key"
CAMINHO_CERTIFICADO = RAIZ / "certs/server.crt"


class ErroIdentidade(ValueError):
    pass


@dataclass(frozen=True)
class IdentidadeServidor:
    chave_privada: rsa.RSAPrivateKey = field(repr=False)
    certificado: bytes


def validar_certificado(certificado_pem, agora=None):
    """Valida o perfil local: RSA >= 2048, SHA256, autoassinatura e vigência."""
    try:
        certificado = x509.load_pem_x509_certificate(certificado_pem)
        publica = certificado.public_key()
        if not isinstance(publica, rsa.RSAPublicKey) or publica.key_size < 2048:
            raise ErroIdentidade("certificado requer RSA de pelo menos 2048 bits")
        instante = agora or datetime.now(timezone.utc)
        if not certificado.not_valid_before_utc <= instante < certificado.not_valid_after_utc:
            raise ErroIdentidade("certificado fora do prazo de validade")
        if certificado.issuer != certificado.subject:
            raise ErroIdentidade("certificado deve ser autoassinado")
        if not isinstance(certificado.signature_hash_algorithm, hashes.SHA256):
            raise ErroIdentidade("certificado requer SHA256")
        if not certificado.extensions.get_extension_for_class(x509.KeyUsage).value.digital_signature:
            raise ErroIdentidade("certificado não permite assinatura digital")
        certificado.verify_directly_issued_by(certificado)
        return certificado
    except (ValueError, TypeError, InvalidSignature, x509.ExtensionNotFound) as erro:
        raise ErroIdentidade("certificado inválido ou fora da validade") from erro


def gerar_identidade(tamanho_rsa=3072, dias=365):
    if tamanho_rsa < 2048 or dias < 1:
        raise ErroIdentidade("use RSA >= 2048 e validade positiva")
    chave = rsa.generate_private_key(public_exponent=65537, key_size=tamanho_rsa)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Mensageria Segura")])
    agora = datetime.now(timezone.utc)
    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome).issuer_name(nome).public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(minutes=1))
        .not_valid_after(agora + timedelta(days=dias))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=True)
        .sign(chave, hashes.SHA256(), rsa_padding=padding.PKCS1v15())
    )
    return IdentidadeServidor(chave, certificado.public_bytes(serialization.Encoding.PEM))


def salvar_identidade(identidade, caminho_chave=CAMINHO_CHAVE, caminho_certificado=CAMINHO_CERTIFICADO):
    """Cria os dois arquivos sem substituir identidades existentes."""
    chave, certificado = Path(caminho_chave), Path(caminho_certificado)
    if chave.resolve() == certificado.resolve() or chave.exists() or certificado.exists():
        raise ErroIdentidade("destino já existe; escolha novos caminhos para gerar a identidade")
    chave.parent.mkdir(parents=True, exist_ok=True)
    certificado.parent.mkdir(parents=True, exist_ok=True)
    dados = identidade.chave_privada.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    descritor = os.open(chave, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descritor, "wb") as arquivo:
            arquivo.write(dados)
        with certificado.open("xb") as arquivo:
            arquivo.write(identidade.certificado)
    except BaseException:
        chave.unlink(missing_ok=True)
        raise


def carregar_certificado_confiavel(caminho=CAMINHO_CERTIFICADO):
    dados = Path(caminho).read_bytes()
    validar_certificado(dados)
    return dados


def carregar_identidade(caminho_chave=CAMINHO_CHAVE, caminho_certificado=CAMINHO_CERTIFICADO):
    certificado_pem = carregar_certificado_confiavel(caminho_certificado)
    certificado = validar_certificado(certificado_pem)
    try:
        chave = serialization.load_pem_private_key(Path(caminho_chave).read_bytes(), password=None)
    except (ValueError, TypeError) as erro:
        raise ErroIdentidade("chave privada inválida") from erro
    if not isinstance(chave, rsa.RSAPrivateKey):
        raise ErroIdentidade("chave privada deve ser RSA")
    if chave.public_key().public_numbers() != certificado.public_key().public_numbers():
        raise ErroIdentidade("chave privada não corresponde ao certificado")
    return IdentidadeServidor(chave, certificado_pem)
