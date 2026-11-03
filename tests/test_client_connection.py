import asyncio
import base64
from uuid import uuid4

import pytest

from src.client.connection import conectar, enviar_relay, fechar, receber_mensagem, registrar
from src.common.framing import ErroQuadro
from src.server.main import iniciar_servidor


async def receber(leitor):
    return await asyncio.wait_for(receber_mensagem(leitor), 1)


@pytest.mark.asyncio
async def testar_cliente_registra_recebe_lista_entrada_e_saida():
    servidor = await iniciar_servidor(porta=0)
    porta = servidor.sockets[0].getsockname()[1]
    id_a, id_b = str(uuid4()), str(uuid4())
    chave_a, chave_b = bytes(range(32)), bytes(range(32, 64))
    leitor_a, escritor_a = await conectar(porta=porta)
    leitor_b, escritor_b = await conectar(porta=porta)
    try:
        await registrar(escritor_a, id_a, chave_a)
        assert await receber(leitor_a) == {"type": "CLIENT_LIST", "clients": []}

        await registrar(escritor_b, id_b, chave_b)
        lista = await receber(leitor_b)
        assert lista["type"] == "CLIENT_LIST"
        assert lista["clients"] == [{"client_id": id_a, "client_public_key": base64.b64encode(chave_a).decode()}]
        entrou = await receber(leitor_a)
        assert entrou == {"type": "CLIENT_JOINED", "client_id": id_b, "client_public_key": base64.b64encode(chave_b).decode()}

        await enviar_relay(escritor_a, id_b, b"\x00\x01opaco")
        relay = await receber(leitor_b)
        assert relay["type"] == "RELAY" and relay["sender_id"] == id_a and relay["recipient_id"] == id_b
        assert base64.b64decode(relay["payload"]) == b"\x00\x01opaco"

        await fechar(escritor_b)
        assert await receber(leitor_a) == {"type": "CLIENT_LEFT", "client_id": id_b}
    finally:
        await fechar(escritor_a)
        servidor.close()
        await servidor.wait_closed()


@pytest.mark.asyncio
async def testar_receber_mensagem_retorna_none_quando_servidor_fecha():
    leitor = asyncio.StreamReader()
    leitor.feed_eof()
    assert await receber_mensagem(leitor) is None


@pytest.mark.asyncio
async def testar_quadro_invalido_do_servidor_e_erro_no_cliente():
    leitor = asyncio.StreamReader()
    leitor.feed_data((64 * 1024 + 1).to_bytes(4, "big"))
    with pytest.raises(ErroQuadro):
        await receber_mensagem(leitor)


@pytest.mark.asyncio
async def testar_registro_rejeita_dados_invalidos_antes_de_enviar():
    with pytest.raises(ValueError):
        await registrar(None, "nao-e-uuid", bytes(32))
    with pytest.raises(ValueError):
        await registrar(None, str(uuid4()), bytes(31))
    with pytest.raises(ValueError):
        await enviar_relay(None, str(uuid4()), b"")
