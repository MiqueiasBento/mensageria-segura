"""Integração: falhas do handshake, controle autenticado e ciclo de sessões."""

import asyncio
import base64
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

import src.server.connection as conexao_servidor
from src.client import connection
from src.client.messaging import Cliente, ErroCliente
from src.common.framing import escrever_quadro
from src.common.protocol import codificar_mensagem
from src.crypto.handshake import ErroHandshake
from src.crypto.identity import gerar_identidade
from src.crypto.key_derivation import gerar_par_efemero
from src.server.main import iniciar_servidor
from src.server.sessions import RegistroSessoes


@asynccontextmanager
async def servidor_teste():
    sessoes = RegistroSessoes()
    servidor = await iniciar_servidor(porta=0, sessoes=sessoes)
    try:
        yield servidor.sockets[0].getsockname()[1], sessoes
    finally:
        for sessao in sessoes.listar_clientes():
            sessao.escritor.close()
        servidor.close()
        await servidor.wait_closed()


async def evento(cliente):
    return await asyncio.wait_for(cliente.eventos.get(), 2)


@pytest.mark.asyncio
async def testar_certificado_errado_impede_registro():
    async with servidor_teste() as (porta, sessoes):
        cliente = Cliente(certificado_confiavel=gerar_identidade(2048).certificado)
        with pytest.raises(ErroHandshake):
            await cliente.conectar(porta=porta)
        assert cliente.peers == {} and cliente._chave_privada is None
        assert sessoes.listar_clientes() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("campo", ["signature", "server_public_key", "salt"])
async def testar_handshake_adulterado_na_rede_fecha_cliente(monkeypatch, campo):
    original = conexao_servidor.criar_handshake

    def adulterar(*argumentos):
        mensagem, canal = original(*argumentos)
        dados = bytearray(base64.b64decode(mensagem[campo]))
        dados[0] ^= 1
        mensagem[campo] = base64.b64encode(dados).decode("ascii")
        return mensagem, canal

    monkeypatch.setattr(conexao_servidor, "criar_handshake", adulterar)
    async with servidor_teste() as (porta, sessoes):
        with pytest.raises(ErroHandshake):
            await Cliente().conectar(porta=porta)
        assert sessoes.listar_clientes() == []


@pytest.mark.asyncio
async def testar_registro_nao_aparece_antes_da_prova_de_posse():
    async with servidor_teste() as (porta, sessoes):
        leitor, escritor = await connection.conectar(porta=porta)
        _, publica = gerar_par_efemero()
        try:
            await connection.registrar(escritor, str(uuid4()), publica)
            assert (await connection.receber_mensagem(leitor))["type"] == "HANDSHAKE"
            assert sessoes.listar_clientes() == []
            await escrever_quadro(escritor, codificar_mensagem({"type": "READY"}))
            assert await asyncio.wait_for(leitor.read(), 2) == b""
            assert sessoes.listar_clientes() == []
        finally:
            await connection.fechar(escritor)


@pytest.mark.asyncio
async def testar_lista_de_chaves_adulterada_apos_mac_e_recusada(monkeypatch):
    escrever_original = conexao_servidor.escrever_quadro

    async def adulterar(escritor, dados):
        from src.common.protocol import decodificar_mensagem
        mensagem = decodificar_mensagem(dados)
        if mensagem["type"] == "AUTH":
            mensagem["message"] = {"type": "CLIENT_LIST", "clients": [{"client_id": str(uuid4()), "client_public_key": base64.b64encode(bytes(32)).decode()}]}
        await escrever_original(escritor, codificar_mensagem(mensagem))

    monkeypatch.setattr(conexao_servidor, "escrever_quadro", adulterar)
    async with servidor_teste() as (porta, _):
        cliente = Cliente()
        with pytest.raises(ErroHandshake):
            await cliente.conectar(porta=porta)
        assert cliente.peers == {}


@pytest.mark.asyncio
async def testar_replay_administrativo_do_servidor_desconecta(monkeypatch):
    original = conexao_servidor.escrever_quadro

    async def duplicar(escritor, dados):
        from src.common.protocol import decodificar_mensagem
        await original(escritor, dados)
        if decodificar_mensagem(dados)["type"] == "AUTH":
            await original(escritor, dados)

    monkeypatch.setattr(conexao_servidor, "escrever_quadro", duplicar)
    async with servidor_teste() as (porta, _):
        cliente = Cliente()
        await cliente.conectar(porta=porta)
        await asyncio.wait_for(cliente.escutar(), 2)
        resultado = await evento(cliente)
        assert resultado.tipo == "desconectado" and "sequência" in resultado.texto


@pytest.mark.asyncio
async def testar_replay_de_comando_do_cliente_fecha_apenas_sua_conexao(registrar_cliente_autenticado):
    async with servidor_teste() as (porta, sessoes):
        leitor, escritor = await connection.conectar(porta=porta)
        try:
            canal, _ = await registrar_cliente_autenticado(leitor, escritor, str(uuid4()))
            await connection.receber_mensagem(leitor, canal)  # CLIENT_LIST
            dados = codificar_mensagem(canal.empacotar({"type": "RELAY", "recipient_id": str(uuid4()), "payload": "YQ=="}))
            await escrever_quadro(escritor, dados)
            assert (await connection.receber_mensagem(leitor, canal))["code"] == "UNKNOWN_CLIENT"
            await escrever_quadro(escritor, dados)
            assert await asyncio.wait_for(leitor.read(), 2) == b""
            assert sessoes.listar_clientes() == []
            novo = Cliente()
            await novo.conectar(porta=porta)
            await novo.fechar()
        finally:
            await connection.fechar(escritor)


@pytest.mark.asyncio
async def testar_mesma_instancia_renova_chaves_e_rejeita_quadro_antigo():
    async with servidor_teste() as (porta, _):
        alice, bob = Cliente(), Cliente()
        await alice.conectar(porta=porta)
        tarefa_a = asyncio.create_task(alice.escutar())
        await bob.conectar(porta=porta)
        tarefa_b = asyncio.create_task(bob.escutar())
        try:
            assert (await evento(alice)).tipo == "entrou"
            quadro_antigo = await alice.enviar_texto(bob.id_cliente, "antes")
            assert (await evento(bob)).tipo == "mensagem"
            publica_antiga = alice.chave_publica
            chave_antiga = bob.peers[alice.id_cliente].chave_recebimento
            await alice.fechar()
            await tarefa_a
            assert (await evento(bob)).tipo == "saiu"
            await alice.conectar(porta=porta)
            tarefa_a = asyncio.create_task(alice.escutar())
            assert (await evento(bob)).tipo == "entrou"
            assert alice.chave_publica != publica_antiga
            assert bob.peers[alice.id_cliente].chave_recebimento != chave_antiga
            await connection.enviar_relay(alice._escritor, bob.id_cliente, quadro_antigo, alice._canal)
            assert (await evento(bob)).tipo == "rejeitada"
            await alice.enviar_texto(bob.id_cliente, "depois")
            assert (await evento(bob)).texto == "depois"
        finally:
            await alice.fechar()
            await bob.fechar()
            await asyncio.gather(tarefa_a, tarefa_b)


@pytest.mark.asyncio
async def testar_salt_comum_na_execucao_e_novo_apos_reinicio():
    salts = []
    for _ in range(2):
        async with servidor_teste() as (porta, _):
            alice, bob = Cliente(), Cliente()
            try:
                await alice.conectar(porta=porta)
                await bob.conectar(porta=porta)
                assert alice._salt == bob._salt and len(alice._salt) == 16
                salts.append(alice._salt)
            finally:
                await alice.fechar()
                await bob.fechar()
    assert salts[0] != salts[1]


@pytest.mark.asyncio
async def testar_id_duplicado_preserva_sessao_original():
    async with servidor_teste() as (porta, sessoes):
        original = Cliente()
        await original.conectar(porta=porta)
        try:
            duplicado = Cliente(original.id_cliente)
            with pytest.raises(ErroCliente, match="CLIENT_LIST"):
                await duplicado.conectar(porta=porta)
            assert len(sessoes.listar_clientes()) == 1
            assert sessoes.obter_cliente(original.id_cliente).chave_publica == base64.b64encode(original.chave_publica).decode()
        finally:
            await original.fechar()


@pytest.mark.asyncio
async def testar_handshake_abandonado_expira(monkeypatch):
    monkeypatch.setattr(conexao_servidor, "TEMPO_HANDSHAKE", 0.05)
    async with servidor_teste() as (porta, sessoes):
        leitor, escritor = await connection.conectar(porta=porta)
        try:
            assert await asyncio.wait_for(leitor.read(), 2) == b""
            assert sessoes.listar_clientes() == []
        finally:
            await connection.fechar(escritor)


@pytest.mark.asyncio
async def testar_registros_simultaneos_preservam_lista_e_eventos():
    async with servidor_teste() as (porta, _):
        clientes = [Cliente() for _ in range(4)]
        tarefas = []
        try:
            await asyncio.gather(*(cliente.conectar(porta=porta) for cliente in clientes))
            tarefas = [asyncio.create_task(cliente.escutar()) for cliente in clientes]
            for cliente in clientes:
                while len(cliente.peers) < len(clientes) - 1:
                    assert (await evento(cliente)).tipo == "entrou"
                assert set(cliente.peers) == {outro.id_cliente for outro in clientes if outro is not cliente}
        finally:
            for cliente in clientes:
                await cliente.fechar()
            await asyncio.gather(*tarefas)


@pytest.mark.asyncio
async def testar_falha_de_escrita_no_destino_preserva_remetente(monkeypatch):
    original = conexao_servidor.enviar

    async def simular_destino_fechado(sessao, mensagem):
        if mensagem["type"] == "RELAY":
            raise BrokenPipeError()
        await original(sessao, mensagem)

    monkeypatch.setattr(conexao_servidor, "enviar", simular_destino_fechado)
    async with servidor_teste() as (porta, sessoes):
        alice, bob = Cliente(), Cliente()
        await alice.conectar(porta=porta)
        tarefa_a = asyncio.create_task(alice.escutar())
        await bob.conectar(porta=porta)
        tarefa_b = asyncio.create_task(bob.escutar())
        try:
            assert (await evento(alice)).tipo == "entrou"
            await alice.enviar_texto(bob.id_cliente, "destino saiu durante o envio")
            recebidos = [await evento(alice), await evento(alice)]
            assert {item.tipo for item in recebidos} == {"erro", "saiu"}
            assert next(item.texto for item in recebidos if item.tipo == "erro") == "UNKNOWN_CLIENT"
            assert sessoes.obter_cliente(alice.id_cliente) is not None
            assert not tarefa_a.done()
        finally:
            await alice.fechar()
            await bob.fechar()
            await asyncio.gather(tarefa_a, tarefa_b)
