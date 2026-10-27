import asyncio
import base64
from uuid import uuid4

import pytest

from src.common.framing import ErroQuadro, ler_quadro, escrever_quadro
from src.common.protocol import decodificar_mensagem, codificar_mensagem
from src.server.main import iniciar_servidor
from src.server.sessions import RegistroSessoes


def registro_cliente(id_cliente, chave):
    return {"type": "REGISTER", "client_id": id_cliente, "client_public_key": base64.b64encode(chave).decode()}


async def receber(leitor):
    return decodificar_mensagem(await asyncio.wait_for(ler_quadro(leitor), 1))


@pytest.mark.asyncio
async def testar_registro_encaminhamento_e_desconexao():
    sessoes = RegistroSessoes()
    servidor = await iniciar_servidor(porta=0, sessoes=sessoes)
    porta = servidor.sockets[0].getsockname()[1]
    id_a, id_b = str(uuid4()), str(uuid4())
    chave_a, chave_b = bytes(range(32)), bytes(range(32, 64))
    leitor_a, escritor_a = await asyncio.open_connection("127.0.0.1", porta)
    leitor_b, escritor_b = await asyncio.open_connection("127.0.0.1", porta)
    try:
        assert len(servidor.sockets) == 1
        await escrever_quadro(escritor_a, codificar_mensagem(registro_cliente(id_a, chave_a)))
        assert await receber(leitor_a) == {"type": "CLIENT_LIST", "clients": []}
        await escrever_quadro(escritor_b, codificar_mensagem(registro_cliente(id_b, chave_b)))
        assert await receber(leitor_b) == {"type": "CLIENT_LIST", "clients": [{"client_id": id_a, "client_public_key": base64.b64encode(chave_a).decode()}]}
        assert await receber(leitor_a) == {"type": "CLIENT_JOINED", "client_id": id_b, "client_public_key": base64.b64encode(chave_b).decode()}
        assert {s.id_cliente for s in sessoes.listar_clientes()} == {id_a, id_b}
        conteudo = base64.b64encode(b"opaque test bytes").decode()
        await escrever_quadro(escritor_a, codificar_mensagem({"type": "RELAY", "recipient_id": id_b, "payload": conteudo}))
        assert await receber(leitor_b) == {"type": "RELAY", "sender_id": id_a, "recipient_id": id_b, "payload": conteudo}
        escritor_b.close()
        await escritor_b.wait_closed()
        assert await receber(leitor_a) == {"type": "CLIENT_LEFT", "client_id": id_b}
        assert [s.id_cliente for s in sessoes.listar_clientes()] == [id_a]
    finally:
        escritor_a.close()
        await escritor_a.wait_closed()
        servidor.close()
        await servidor.wait_closed()


@pytest.mark.asyncio
async def testar_desconexao_por_quadro_invalido():
    servidor = await iniciar_servidor(porta=0)
    leitor, escritor = await asyncio.open_connection("127.0.0.1", servidor.sockets[0].getsockname()[1])
    try:
        escritor.write((65537).to_bytes(4, "big"))
        await escritor.drain()
        assert await asyncio.wait_for(leitor.read(), 1) == b""
    finally:
        escritor.close()
        await escritor.wait_closed()
        servidor.close()
        await servidor.wait_closed()


@pytest.mark.asyncio
async def testar_leitura_e_tamanho_do_quadro():
    leitor = asyncio.StreamReader()
    leitor.feed_data((3).to_bytes(4, "big") + b"abc")
    leitor.feed_eof()
    assert await ler_quadro(leitor) == b"abc"
    assert await ler_quadro(leitor) is None
    quadro_invalido = asyncio.StreamReader()
    quadro_invalido.feed_data((0).to_bytes(4, "big"))
    with pytest.raises(ErroQuadro):
        await ler_quadro(quadro_invalido)
