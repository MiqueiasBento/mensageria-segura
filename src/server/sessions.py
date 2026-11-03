"""Registro de conexões que provaram posse da chave efêmera."""

import asyncio
from dataclasses import dataclass, field

from src.crypto.handshake import CanalAutenticado


@dataclass
class Sessao:
    id_cliente: str
    chave_publica: str
    escritor: asyncio.StreamWriter
    canal: CanalAutenticado = field(repr=False)
    trava_envio: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class RegistroSessoes:
    def __init__(self, limite=128):
        self._sessoes = {}
        self.limite = limite
        # Ordena listas, entradas e saídas. Escritas têm prazo limitado.
        self.trava = asyncio.Lock()

    def registrar_cliente(self, id_cliente, chave_publica, escritor, canal):
        if id_cliente in self._sessoes:
            raise ValueError("identificador já conectado")
        if len(self._sessoes) >= self.limite:
            raise ValueError("limite de clientes atingido")
        sessao = Sessao(id_cliente, chave_publica, escritor, canal)
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
