"""Identidade temporária de testes; a produção nunca usa confiança automática."""

import pytest

from src.client import connection
from src.common.framing import escrever_quadro
from src.common.protocol import codificar_mensagem
from src.crypto.handshake import validar_handshake
from src.crypto.identity import gerar_identidade
from src.crypto.key_derivation import gerar_par_efemero


@pytest.fixture(scope="session")
def identidade_teste():
    return gerar_identidade(tamanho_rsa=2048)


@pytest.fixture(autouse=True)
def provisionar_identidade_de_teste(monkeypatch, identidade_teste):
    import src.server.main as servidor
    import src.client.messaging as cliente
    carregar_original = cliente.carregar_certificado_confiavel
    monkeypatch.setattr(servidor, "carregar_identidade", lambda: identidade_teste)
    monkeypatch.setattr(cliente, "carregar_certificado_confiavel",
                        lambda caminho=None: carregar_original(caminho) if caminho is not None else identidade_teste.certificado)


@pytest.fixture
def registrar_cliente_autenticado(identidade_teste):
    async def registrar(leitor, escritor, id_cliente):
        privada, publica = gerar_par_efemero()
        await connection.registrar(escritor, id_cliente, publica)
        resposta = await connection.receber_mensagem(leitor)
        _, canal = validar_handshake(resposta, identidade_teste.certificado, privada, publica, id_cliente)
        await escrever_quadro(escritor, codificar_mensagem(canal.empacotar({"type": "READY"})))
        return canal, publica
    return registrar
