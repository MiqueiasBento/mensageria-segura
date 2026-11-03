"""Chat de terminal. Executar com: python -m src.client.main [--host H] [--port P]

Comandos:
    /peers               lista os peers (id curto + fingerprint da chave publica)
    /msg <id> <texto>    envia texto cifrado E2E (aceita prefixo unico do id)
    /id                  mostra o proprio client_id
    /ajuda               mostra os comandos
    /sair                desconecta
"""

import argparse
import asyncio
import sys
import threading

from src.client.connection import ENDERECO_PADRAO, PORTA_PADRAO
from src.client.messaging import Cliente, ErroCliente, impressao_digital

AJUDA = __doc__.split("Comandos:", 1)[1].rstrip()


def curto(id_cliente):
    return id_cliente[:8]


def ler_teclado(laco, fila):
    """Thread daemon: le stdin sem bloquear o asyncio e sem travar o encerramento."""
    for linha in sys.stdin:
        laco.call_soon_threadsafe(fila.put_nowait, linha.rstrip("\r\n"))
    laco.call_soon_threadsafe(fila.put_nowait, None)


async def mostrar_eventos(cliente):
    while True:
        evento = await cliente.eventos.get()
        if evento.tipo == "mensagem":
            print(f"[{curto(evento.id_peer)}] {evento.texto}")
        elif evento.tipo == "entrou":
            print(f"* {curto(evento.id_peer)} entrou")
        elif evento.tipo == "saiu":
            print(f"* {curto(evento.id_peer)} saiu")
        elif evento.tipo == "rejeitada":
            origem = curto(evento.id_peer) if evento.id_peer else "?"
            print(f"! mensagem de {origem} rejeitada: {evento.texto}")
        elif evento.tipo == "erro":
            print(f"! erro do servidor: {evento.texto}")
        elif evento.tipo == "desconectado":
            print(f"* desconectado: {evento.texto}")
            return


async def executar_comando(cliente, linha):
    """Retorna False quando o usuario pede para sair."""
    comando, _, resto = linha.strip().partition(" ")
    if not comando:
        return True
    if comando == "/sair":
        return False
    if comando == "/peers":
        if not cliente.peers:
            print("(nenhum peer conectado)")
        for id_peer, estado in cliente.peers.items():
            print(f"  {curto(id_peer)}  {id_peer}  fp={impressao_digital(estado.chave_publica)}")
    elif comando == "/id":
        print(f"  {cliente.id_cliente}  fp={impressao_digital(cliente.chave_publica)}")
    elif comando == "/msg":
        prefixo, _, texto = resto.strip().partition(" ")
        if not prefixo or not texto:
            print("uso: /msg <id> <texto>")
            return True
        try:
            id_peer = cliente.resolver_peer(prefixo)
            await cliente.enviar_texto(id_peer, texto)
        except (ErroCliente, ValueError) as erro:
            print(f"! nao enviado: {erro}")
    else:
        print(AJUDA)
    return True


async def principal(endereco, porta):
    cliente = Cliente()
    try:
        await cliente.conectar(endereco, porta)
    except (ConnectionError, OSError, ValueError, ErroCliente) as erro:
        print(f"Falha ao conectar em {endereco}:{porta}: {erro}")
        return 1

    print(f"Conectado como {cliente.id_cliente} ({curto(cliente.id_cliente)})")
    print(f"{len(cliente.peers)} peer(s) online. Digite /ajuda para ver os comandos.")

    linhas = asyncio.Queue()
    threading.Thread(target=ler_teclado, args=(asyncio.get_running_loop(), linhas), daemon=True).start()
    escuta = asyncio.create_task(cliente.escutar())
    tela = asyncio.create_task(mostrar_eventos(cliente))
    try:
        while not tela.done():
            proxima = asyncio.create_task(linhas.get())
            await asyncio.wait({proxima, tela}, return_when=asyncio.FIRST_COMPLETED)
            if not proxima.done():
                proxima.cancel()
                break
            linha = proxima.result()
            if linha is None or not await executar_comando(cliente, linha):
                break
    finally:
        await cliente.fechar()
        await escuta
        await tela
    return 0


def main():
    argumentos = argparse.ArgumentParser(description="Cliente de mensageria segura")
    argumentos.add_argument("--host", default=ENDERECO_PADRAO)
    argumentos.add_argument("--port", type=int, default=PORTA_PADRAO)
    opcoes = argumentos.parse_args()
    try:
        return asyncio.run(principal(opcoes.host, opcoes.port))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
