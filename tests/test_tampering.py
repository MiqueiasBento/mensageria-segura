import uuid

import pytest

from src.client.peers import ErroMensagem, criar_estado_peer, preparar_envio, processar_recebimento
from src.crypto.key_derivation import gerar_par_efemero

# Regioes do quadro E2E: (inicio, fim) em bytes.
REGIOES = {
    "nonce_iv_base": (0, 4),
    "nonce_seq": (4, 12),
    "sender_id": (12, 28),
    "recipient_id": (28, 44),
    "seq_no": (44, 52),
    "ciphertext": (52, -16),
    "tag": (-16, None),
}


def criar_clientes(quantidade):
    """Retorna ids e chaves de N clientes."""
    clientes = []
    for _ in range(quantidade):
        privada, publica = gerar_par_efemero()
        clientes.append((uuid.uuid4().bytes, privada, publica))
    return clientes


def estado(de, para):
    meu_id, minha_privada, _ = de
    id_peer, _, publica_peer = para
    return meu_id, criar_estado_peer(minha_privada, meu_id, id_peer, publica_peer, SALT_TESTE)


def inverter_bit(quadro, posicao):
    adulterado = bytearray(quadro)
    adulterado[posicao] ^= 0x01
    return bytes(adulterado)


@pytest.mark.parametrize("regiao", REGIOES)
@pytest.mark.parametrize("onde", ["primeiro_byte", "ultimo_byte"])
def testar_bit_invertido_em_cada_regiao_e_rejeitado(regiao, onde):
    a, b = criar_clientes(2)
    id_a, estado_a = estado(a, b)
    id_b, estado_b = estado(b, a)
    quadro = preparar_envio(estado_a, id_a, b"conteudo protegido")

    inicio, fim = REGIOES[regiao]
    posicoes = range(len(quadro))[inicio:fim]
    posicao = posicoes[0] if onde == "primeiro_byte" else posicoes[-1]

    with pytest.raises(ErroMensagem):
        processar_recebimento(estado_b, id_b, inverter_bit(quadro, posicao))
    # O estado nao mudou: o quadro original ainda e aceito.
    assert estado_b.seq_recebimento == -1
    assert processar_recebimento(estado_b, id_b, quadro) == b"conteudo protegido"


def testar_quadro_destinado_a_outro_cliente_e_rejeitado():
    a, b, c = criar_clientes(3)
    id_a, a_para_c = estado(a, c)
    id_b, b_de_a = estado(b, a)
    quadro_para_c = preparar_envio(a_para_c, id_a, b"so para C")
    with pytest.raises(ErroMensagem, match="another client"):
        processar_recebimento(b_de_a, id_b, quadro_para_c)


def testar_quadro_de_outro_remetente_e_rejeitado():
    a, b, c = criar_clientes(3)
    id_c, c_para_b = estado(c, b)
    id_b, b_de_a = estado(b, a)
    with pytest.raises(ErroMensagem, match="sender_id"):
        processar_recebimento(b_de_a, id_b, preparar_envio(c_para_b, id_c, b"sou C"))


def testar_remetente_falsificado_sem_a_chave_e_rejeitado():
    # C troca o sender_id para se passar por A, mas cifra com a chave do par C-B.
    a, b, c = criar_clientes(3)
    id_a = a[0]
    id_c, c_para_b = estado(c, b)
    id_b, b_de_a = estado(b, a)
    quadro = bytearray(preparar_envio(c_para_b, id_c, b"sou A, confie"))
    quadro[12:28] = id_a
    with pytest.raises(ErroMensagem, match="authentication"):
        processar_recebimento(b_de_a, id_b, bytes(quadro))


@pytest.mark.parametrize(
    "quadro",
    [b"", b"\x00" * 67, "texto"],
    ids=["vazio", "menor_que_o_minimo", "str"],
)
def testar_quadro_malformado_e_rejeitado(quadro):
    a, b = criar_clientes(2)
    id_b, b_de_a = estado(b, a)
    with pytest.raises(ErroMensagem, match="malformed"):
        processar_recebimento(b_de_a, id_b, quadro)


# Vetor fixo apenas nos testes unitários; a rede exige salt autenticado.
SALT_TESTE = bytes(16)
