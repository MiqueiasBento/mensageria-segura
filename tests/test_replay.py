import dataclasses
import uuid

import pytest

from src.client.peers import (
    ErroMensagem,
    ErroReplay,
    criar_estado_peer,
    preparar_envio,
    processar_recebimento,
)
from src.crypto.key_derivation import SALT_PROVISORIO, gerar_par_efemero


def criar_par():
    """Retorna (id_a, estado_de_A_para_B, id_b, estado_de_B_para_A)."""
    privada_a, publica_a = gerar_par_efemero()
    privada_b, publica_b = gerar_par_efemero()
    id_a, id_b = uuid.uuid4().bytes, uuid.uuid4().bytes
    estado_a = criar_estado_peer(privada_a, id_a, id_b, publica_b, SALT_PROVISORIO)
    estado_b = criar_estado_peer(privada_b, id_b, id_a, publica_a, SALT_PROVISORIO)
    return id_a, estado_a, id_b, estado_b


def testar_estados_dos_dois_lados_tem_chaves_cruzadas():
    _, estado_a, _, estado_b = criar_par()
    assert estado_a.chave_envio == estado_b.chave_recebimento
    assert estado_b.chave_envio == estado_a.chave_recebimento
    assert estado_a.seq_envio == 0 and estado_a.seq_recebimento == -1


def testar_repr_do_estado_nao_mostra_segredos():
    _, estado_a, _, _ = criar_par()
    texto = repr(estado_a)
    for segredo in (estado_a.chave_envio, estado_a.chave_recebimento, estado_a.iv_base_envio):
        assert repr(segredo) not in texto


def testar_tres_mensagens_aceitas_em_ordem():
    id_a, estado_a, id_b, estado_b = criar_par()
    for numero in range(3):
        quadro = preparar_envio(estado_a, id_a, f"mensagem {numero}".encode())
        assert processar_recebimento(estado_b, id_b, quadro) == f"mensagem {numero}".encode()
    assert estado_a.seq_envio == 3
    assert estado_b.seq_recebimento == 2


def testar_conversa_nos_dois_sentidos_usa_contadores_independentes():
    id_a, estado_a, id_b, estado_b = criar_par()
    assert processar_recebimento(estado_b, id_b, preparar_envio(estado_a, id_a, b"oi B")) == b"oi B"
    assert processar_recebimento(estado_a, id_a, preparar_envio(estado_b, id_b, b"oi A")) == b"oi A"
    assert processar_recebimento(estado_a, id_a, preparar_envio(estado_b, id_b, b"tudo bem?")) == b"tudo bem?"
    assert (estado_a.seq_envio, estado_a.seq_recebimento) == (1, 1)
    assert (estado_b.seq_envio, estado_b.seq_recebimento) == (2, 0)


def testar_reenviar_a_mesma_mensagem_e_replay():
    id_a, estado_a, id_b, estado_b = criar_par()
    quadros = [preparar_envio(estado_a, id_a, texto) for texto in (b"um", b"dois", b"tres")]
    processar_recebimento(estado_b, id_b, quadros[0])
    processar_recebimento(estado_b, id_b, quadros[1])
    with pytest.raises(ErroReplay):
        processar_recebimento(estado_b, id_b, quadros[1])
    assert processar_recebimento(estado_b, id_b, quadros[2]) == b"tres"


def testar_reenviar_a_primeira_depois_da_terceira_e_replay():
    id_a, estado_a, id_b, estado_b = criar_par()
    quadros = [preparar_envio(estado_a, id_a, texto) for texto in (b"um", b"dois", b"tres")]
    for quadro in quadros:
        processar_recebimento(estado_b, id_b, quadro)
    with pytest.raises(ErroReplay):
        processar_recebimento(estado_b, id_b, quadros[0])
    assert estado_b.seq_recebimento == 2


def testar_seq_pode_pular_mas_nao_voltar():
    # O TCP entrega em ordem; um seq menor que o ultimo aceito so pode ser replay.
    id_a, estado_a, id_b, estado_b = criar_par()
    quadros = [preparar_envio(estado_a, id_a, texto) for texto in (b"0", b"1", b"2")]
    processar_recebimento(estado_b, id_b, quadros[0])
    assert processar_recebimento(estado_b, id_b, quadros[2]) == b"2"
    with pytest.raises(ErroReplay):
        processar_recebimento(estado_b, id_b, quadros[1])


def testar_quadro_com_tag_invalida_nao_avanca_o_contador():
    id_a, estado_a, id_b, estado_b = criar_par()
    legitimo = preparar_envio(estado_a, id_a, b"legitimo")
    adulterado = bytearray(legitimo)
    adulterado[-1] ^= 0x01
    with pytest.raises(ErroMensagem):
        processar_recebimento(estado_b, id_b, bytes(adulterado))
    assert estado_b.seq_recebimento == -1
    assert estado_b.iv_base_recebimento is None
    assert processar_recebimento(estado_b, id_b, legitimo) == b"legitimo"


def testar_seq_forjado_muito_alto_nao_trava_a_conversa():
    # Ataque: quadro com seq = 10^18 (nonce coerente) mas sem a chave para gerar a tag.
    id_a, estado_a, id_b, estado_b = criar_par()
    legitimo = preparar_envio(estado_a, id_a, b"proxima mensagem")
    seq_forjado = (10**18).to_bytes(8, "big")
    forjado = bytearray(legitimo)
    forjado[4:12] = seq_forjado    # parte seq do nonce
    forjado[44:52] = seq_forjado   # campo seq_no do cabecalho
    with pytest.raises(ErroMensagem):
        processar_recebimento(estado_b, id_b, bytes(forjado))
    assert processar_recebimento(estado_b, id_b, legitimo) == b"proxima mensagem"


def testar_iv_base_fica_fixo_apos_o_primeiro_quadro():
    id_a, estado_a, id_b, estado_b = criar_par()
    processar_recebimento(estado_b, id_b, preparar_envio(estado_a, id_a, b"primeira"))
    assert estado_b.iv_base_recebimento == estado_a.iv_base_envio

    # Mesmas chaves, outro IV_base: a tag seria valida, mas o IV mudou no meio da sessao.
    outro_iv = bytes(b ^ 0xFF for b in estado_a.iv_base_envio)
    remetente_trocado = dataclasses.replace(estado_a, iv_base_envio=outro_iv)
    with pytest.raises(ErroMensagem, match="IV_base"):
        processar_recebimento(estado_b, id_b, preparar_envio(remetente_trocado, id_a, b"segunda"))
    assert estado_b.seq_recebimento == 0


def testar_falha_ao_cifrar_nao_consome_o_seq():
    id_a, estado_a, _, _ = criar_par()
    with pytest.raises(ValueError):
        preparar_envio(estado_a, id_a, b"x" * 4097)
    assert estado_a.seq_envio == 0


def testar_contador_de_envio_esgotado_e_rejeitado():
    id_a, estado_a, _, _ = criar_par()
    estado_a.seq_envio = 2**64
    with pytest.raises(ErroMensagem):
        preparar_envio(estado_a, id_a, b"x")
