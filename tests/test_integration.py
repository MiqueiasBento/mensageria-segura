"""Servidor real + clientes reais: E2E, replay/adulteracao pela rede, reconexao e logs."""

import asyncio
import base64
from contextlib import asynccontextmanager

import pytest

import src.server.connection as conexao_servidor
from src.client.messaging import Cliente
from src.common.framing import escrever_quadro, ler_quadro
from src.common.protocol import codificar_mensagem
from src.server.main import iniciar_servidor


@asynccontextmanager
async def servidor_local():
    servidor = await iniciar_servidor(porta=0)
    try:
        yield servidor.sockets[0].getsockname()[1]
    finally:
        servidor.close()
        await servidor.wait_closed()


@asynccontextmanager
async def clientes_conectados(porta, quantidade):
    """Conecta os clientes em ordem e consome os eventos "entrou" gerados entre eles."""
    clientes, tarefas = [], []
    try:
        for _ in range(quantidade):
            novo = Cliente()
            await novo.conectar(porta=porta)
            for anterior in clientes:
                assert await proximo_evento(anterior) == ("entrou", novo.id_cliente, None)
            clientes.append(novo)
            tarefas.append(asyncio.create_task(novo.escutar()))
        yield clientes
    finally:
        for cliente in clientes:
            await cliente.fechar()
        await asyncio.gather(*tarefas, return_exceptions=True)


async def proximo_evento(cliente, tempo=1):
    evento = await asyncio.wait_for(cliente.eventos.get(), tempo)
    return evento.tipo, evento.id_peer, evento.texto


def sem_evento(cliente):
    return cliente.eventos.empty()


def interceptar_relay(monkeypatch, alterar=None, repetir=1):
    """Troca o relay do servidor por um que registra (e opcionalmente altera/repete) o payload."""
    original = conexao_servidor.encaminhar
    vistos = []

    async def relay_espiao(mensagem, remetente, sessoes, enviar):
        quadro = base64.b64decode(mensagem["payload"])
        vistos.append(quadro)
        if alterar is not None:
            mensagem = {**mensagem, "payload": base64.b64encode(alterar(quadro)).decode()}
        for _ in range(repetir):
            await original(mensagem, remetente, sessoes, enviar)

    monkeypatch.setattr(conexao_servidor, "encaminhar", relay_espiao)
    return vistos


@pytest.mark.asyncio
async def testar_dois_clientes_trocam_mensagens_e2e(monkeypatch):
    vistos = interceptar_relay(monkeypatch)
    async with servidor_local() as porta, clientes_conectados(porta, 2) as (alice, bob):
        assert set(alice.peers) == {bob.id_cliente} and set(bob.peers) == {alice.id_cliente}

        await alice.enviar_texto(bob.id_cliente, "olá, Bob")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "olá, Bob")
        await bob.enviar_texto(alice.id_cliente, "oi, Alice")
        assert await proximo_evento(alice) == ("mensagem", bob.id_cliente, "oi, Alice")

    # O servidor so viu quadros cifrados: o texto nunca passou em claro.
    assert len(vistos) == 2
    for quadro, texto in zip(vistos, ("olá, Bob", "oi, Alice")):
        assert texto.encode() not in quadro
        assert len(quadro) == 52 + len(texto.encode()) + 16


@pytest.mark.asyncio
async def testar_so_o_destinatario_recebe_e_decifra():
    async with servidor_local() as porta, clientes_conectados(porta, 3) as (alice, bob, carol):
        await alice.enviar_texto(bob.id_cliente, "so para o Bob")
        await alice.enviar_texto(carol.id_cliente, "so para a Carol")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "so para o Bob")
        assert await proximo_evento(carol) == ("mensagem", alice.id_cliente, "so para a Carol")
        # Chaves por par: as chaves de A->B e A->C sao diferentes.
        assert alice.peers[bob.id_cliente].chave_envio != alice.peers[carol.id_cliente].chave_envio
        await asyncio.sleep(0.05)
        assert sem_evento(bob) and sem_evento(carol)


@pytest.mark.asyncio
async def testar_replay_pela_rede_e_rejeitado(monkeypatch):
    # Servidor malicioso: entrega cada quadro duas vezes.
    interceptar_relay(monkeypatch, repetir=2)
    async with servidor_local() as porta, clientes_conectados(porta, 2) as (alice, bob):
        await alice.enviar_texto(bob.id_cliente, "pagar 10 reais")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "pagar 10 reais")
        tipo, id_peer, motivo = await proximo_evento(bob)
        assert (tipo, id_peer) == ("rejeitada", alice.id_cliente) and "replay" in motivo

        # A conversa continua normalmente depois do replay rejeitado.
        await alice.enviar_texto(bob.id_cliente, "proxima")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "proxima")


@pytest.mark.asyncio
@pytest.mark.parametrize("posicao", [0, 12, 28, 44, 52, -1], ids=["nonce", "sender", "recipient", "seq", "cifrado", "tag"])
async def testar_bitflip_pela_rede_e_rejeitado(monkeypatch, posicao):
    alterados = []

    def inverter_um_bit(quadro):
        if alterados:          # so o primeiro quadro e adulterado
            return quadro
        adulterado = bytearray(quadro)
        adulterado[posicao] ^= 0x01
        alterados.append(True)
        return bytes(adulterado)

    interceptar_relay(monkeypatch, alterar=inverter_um_bit)
    async with servidor_local() as porta, clientes_conectados(porta, 2) as (alice, bob):
        await alice.enviar_texto(bob.id_cliente, "mensagem original")
        tipo, id_peer, _ = await proximo_evento(bob)
        assert (tipo, id_peer) == ("rejeitada", alice.id_cliente)
        assert bob.peers[alice.id_cliente].seq_recebimento == -1

        await alice.enviar_texto(bob.id_cliente, "segunda")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "segunda")


@pytest.mark.asyncio
async def testar_reconexao_gera_chaves_novas():
    async with servidor_local() as porta, clientes_conectados(porta, 2) as (alice, bob):
        await alice.enviar_texto(bob.id_cliente, "antes")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "antes")
        estado_antigo = bob.peers[alice.id_cliente]

        await alice.fechar()
        assert (await proximo_evento(alice))[0] == "desconectado"
        assert await proximo_evento(bob) == ("saiu", alice.id_cliente, None)
        assert alice.id_cliente not in bob.peers and alice.peers == {}

        # Mesmo client_id, nova execucao: par efemero, chaves e contadores novos.
        alice2 = Cliente(alice.id_cliente)
        await alice2.conectar(porta=porta)
        tarefa = asyncio.create_task(alice2.escutar())
        try:
            assert await proximo_evento(bob) == ("entrou", alice.id_cliente, None)
            estado_novo = bob.peers[alice.id_cliente]
            assert alice2.chave_publica != alice.chave_publica
            assert estado_novo.chave_publica != estado_antigo.chave_publica
            assert estado_novo.chave_recebimento != estado_antigo.chave_recebimento
            assert estado_novo.chave_envio != estado_antigo.chave_envio
            assert (estado_novo.seq_envio, estado_novo.seq_recebimento) == (0, -1)

            await alice2.enviar_texto(bob.id_cliente, "depois")
            assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "depois")
            await bob.enviar_texto(alice.id_cliente, "bem-vinda de volta")
            assert await proximo_evento(alice2) == ("mensagem", bob.id_cliente, "bem-vinda de volta")
        finally:
            await alice2.fechar()
            await tarefa


@pytest.mark.asyncio
async def testar_cliente_desconecta_com_quadro_invalido_do_servidor():
    async def servidor_quebrado(leitor, escritor):
        await ler_quadro(leitor)   # REGISTER
        await escrever_quadro(escritor, codificar_mensagem({"type": "CLIENT_LIST", "clients": []}))
        escritor.write((64 * 1024 + 1).to_bytes(4, "big"))   # comprimento invalido
        await escritor.drain()
        await leitor.read()        # espera o cliente fechar
        escritor.close()

    servidor = await asyncio.start_server(servidor_quebrado, "127.0.0.1", 0)
    try:
        cliente = Cliente()
        await cliente.conectar(porta=servidor.sockets[0].getsockname()[1])
        await asyncio.wait_for(cliente.escutar(), 1)
        tipo, _, motivo = await proximo_evento(cliente)
        assert tipo == "desconectado" and "invalid frame length" in motivo
        assert cliente.peers == {}
    finally:
        servidor.close()
        await servidor.wait_closed()


@pytest.mark.asyncio
async def testar_logs_nao_expoem_segredos_nem_conteudo(capsys):
    async with servidor_local() as porta, clientes_conectados(porta, 2) as (alice, bob):
        await alice.enviar_texto(bob.id_cliente, "segredo-de-teste")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "segredo-de-teste")
        estado = alice.peers[bob.id_cliente]
        segredos = [estado.chave_envio, estado.chave_recebimento, estado.iv_base_envio]
        texto_repr = repr(alice) + repr(estado)

    saida = capsys.readouterr()
    log = saida.out + saida.err + texto_repr
    assert "segredo-de-teste" not in log
    for segredo in segredos:
        assert segredo.hex() not in log
        assert base64.b64encode(segredo).decode() not in log
        assert repr(segredo) not in log


@pytest.mark.asyncio
async def testar_mensagem_error_do_servidor_nao_derruba_o_cliente():
    async with servidor_local() as porta, clientes_conectados(porta, 2) as (alice, bob):
        alice.processar_mensagem({"type": "ERROR", "code": "UNKNOWN_CLIENT"})
        assert await proximo_evento(alice) == ("erro", None, "UNKNOWN_CLIENT")
        await alice.enviar_texto(bob.id_cliente, "ainda conectada")
        assert await proximo_evento(bob) == ("mensagem", alice.id_cliente, "ainda conectada")
