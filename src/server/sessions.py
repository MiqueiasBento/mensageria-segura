"""Registro de clientes ativos mantido somente na memória do servidor."""

from dataclasses import dataclass, field
import asyncio


@dataclass
class Sessao:
    id_cliente: str
    chave_publica: str
    escritor: asyncio.StreamWriter
    trava_envio: asyncio.Lock = field(default_factory=asyncio.Lock)


class RegistroSessoes:
    def __init__(self):
        self._sessoes = {}

    def registrar_cliente(self, id_cliente, chave_publica, escritor):
        if id_cliente in self._sessoes:
            raise ValueError("client_id already connected")
        sessao = Sessao(id_cliente, chave_publica, escritor)
        self._sessoes[id_cliente] = sessao
        return sessao

    def obter_cliente(self, id_cliente):
        return self._sessoes.get(id_cliente)

    def remover_cliente(self, id_cliente, escritor):
        sessao = self._sessoes.get(id_cliente)
        if sessao is not None and sessao.escritor is escritor:
            del self._sessoes[id_cliente]
            return sessao
        return None

    def listar_clientes(self):
        return list(self._sessoes.values())
