"""Identidade, transcrição RSA-PSS e autenticação administrativa."""

import copy
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.crypto.handshake import (
    ErroHandshake, criar_handshake, validar_handshake, para_base64,
)
from src.crypto.identity import (
    ErroIdentidade, carregar_identidade, gerar_identidade, salvar_identidade, validar_certificado,
)
from src.crypto.key_derivation import gerar_par_efemero


@pytest.fixture(scope="module")
def identidade():
    return gerar_identidade(tamanho_rsa=2048)


def par_autenticado(identidade):
    privada, publica = gerar_par_efemero()
    id_cliente, salt = str(uuid4()), os.urandom(16)
    mensagem, servidor = criar_handshake(identidade, publica, id_cliente, salt)
    recebido, cliente = validar_handshake(mensagem, identidade.certificado, privada, publica, id_cliente)
    assert recebido == salt
    return mensagem, servidor, cliente, privada, publica, id_cliente


def testar_handshake_e_controle_nos_dois_sentidos(identidade):
    _, servidor, cliente, *_ = par_autenticado(identidade)
    assert servidor.chave_envio != cliente.chave_envio
    assert servidor.desempacotar(cliente.empacotar({"type": "READY"})) == {"type": "READY"}
    assert cliente.desempacotar(servidor.empacotar({"type": "CLIENT_LIST", "clients": []})) == {"type": "CLIENT_LIST", "clients": []}


@pytest.mark.parametrize("campo", ["signature", "server_public_key", "salt"])
def testar_adulteracao_do_handshake_rejeitada(identidade, campo):
    mensagem, _, _, privada, publica, id_cliente = par_autenticado(identidade)
    import base64
    dados = bytearray(base64.b64decode(mensagem[campo]))
    dados[0] ^= 1
    mensagem[campo] = para_base64(dados)
    with pytest.raises(ErroHandshake):
        validar_handshake(mensagem, identidade.certificado, privada, publica, id_cliente)


def testar_certificado_nao_confiavel_rejeitado(identidade):
    mensagem, _, _, privada, publica, id_cliente = par_autenticado(identidade)
    with pytest.raises(ErroHandshake):
        validar_handshake(mensagem, gerar_identidade(2048).certificado, privada, publica, id_cliente)


@pytest.mark.parametrize("alterar", ["id", "chave", "versao", "base64"])
def testar_handshake_vincula_identidade_e_chave_do_cliente(identidade, alterar):
    mensagem, _, _, privada, publica, id_cliente = par_autenticado(identidade)
    if alterar == "id":
        id_cliente = str(uuid4())
    elif alterar == "chave":
        privada, publica = gerar_par_efemero()
    elif alterar == "versao":
        mensagem["version"] = 0
    else:
        mensagem["certificate"] = "%%%"
    with pytest.raises(ErroHandshake):
        validar_handshake(mensagem, identidade.certificado, privada, publica, id_cliente)


def testar_chave_de_ordem_baixa_recusada(identidade):
    with pytest.raises(ErroHandshake):
        criar_handshake(identidade, bytes(32), str(uuid4()), os.urandom(16))


@pytest.mark.parametrize("campo", ["message", "session_id", "seq_no", "mac"])
def testar_controle_adulterado_nao_avanca_contador(identidade, campo):
    _, servidor, cliente, *_ = par_autenticado(identidade)
    original = servidor.empacotar({"type": "CLIENT_LIST", "clients": []})
    alterado = copy.deepcopy(original)
    alterado[campo] = {"type": "CLIENT_LEFT", "client_id": str(uuid4())} if campo == "message" else (99 if campo == "seq_no" else "invalido")
    with pytest.raises(ErroHandshake):
        cliente.desempacotar(alterado)
    assert cliente.seq_recebimento == 0
    assert cliente.desempacotar(original)["type"] == "CLIENT_LIST"
    with pytest.raises(ErroHandshake):
        cliente.desempacotar(original)


def testar_controle_de_outra_conexao_rejeitado(identidade):
    _, servidor, _, *_ = par_autenticado(identidade)
    _, _, cliente, *_ = par_autenticado(identidade)
    with pytest.raises(ErroHandshake):
        cliente.desempacotar(servidor.empacotar({"type": "CLIENT_LIST", "clients": []}))


def testar_certificado_vencido_rejeitado(identidade):
    with pytest.raises(ErroIdentidade):
        validar_certificado(identidade.certificado, datetime.now(timezone.utc) + timedelta(days=366))


def testar_persistencia_identidade_permissoes_e_nao_sobrescrita(identidade, tmp_path):
    chave, certificado = tmp_path / "server.key", tmp_path / "server.crt"
    salvar_identidade(identidade, chave, certificado)
    assert chave.stat().st_mode & 0o777 == 0o600
    assert carregar_identidade(chave, certificado).certificado == identidade.certificado
    with pytest.raises(ErroIdentidade):
        salvar_identidade(identidade, chave, certificado)
    assert carregar_identidade(chave, certificado).chave_privada.private_numbers() == identidade.chave_privada.private_numbers()


def testar_chave_incompativel_com_certificado(identidade, tmp_path):
    chave, certificado = tmp_path / "server.key", tmp_path / "server.crt"
    salvar_identidade(gerar_identidade(2048), chave, certificado)
    certificado.write_bytes(identidade.certificado)
    with pytest.raises(ErroIdentidade):
        carregar_identidade(chave, certificado)
