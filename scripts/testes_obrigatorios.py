"""Roda os testes ligados às especificações operacionais do enunciado, por item.

Executar na raiz do projeto:
    python -m scripts.testes_obrigatorios
"""

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

GRUPOS = [
    ("1. Dois clientes trocando mensagens E2E", [
        "tests/test_integration.py::testar_dois_clientes_trocam_mensagens_e2e",
        "tests/test_integration.py::testar_so_o_destinatario_recebe_e_decifra",
    ]),
    ("1. Bitflip no tráfego (tag GCM falha)", [
        "tests/test_integration.py::testar_bitflip_pela_rede_e_rejeitado",
        "tests/test_tampering.py::testar_bit_invertido_em_cada_regiao_e_rejeitado",
        "tests/test_aead.py::testar_bit_invertido_no_cifrado_falha_a_tag",
    ]),
    ("1. Replay (seq_no já usado)", [
        "tests/test_integration.py::testar_replay_pela_rede_e_rejeitado",
        "tests/test_replay.py::testar_reenviar_a_mesma_mensagem_e_replay",
        "tests/test_replay.py::testar_reenviar_a_primeira_depois_da_terceira_e_replay",
    ]),
    ("1. Framing inválido (erro e desconexão segura)", [
        "tests/test_initial_server.py::testar_desconexao_por_quadro_invalido",
        "tests/test_framing.py::testar_tamanho_zero_e_rejeitado",
        "tests/test_framing.py::testar_tamanho_acima_do_limite_e_rejeitado_sem_ler_o_corpo",
        "tests/test_framing.py::testar_cabecalho_incompleto_e_rejeitado",
        "tests/test_framing.py::testar_corpo_incompleto_e_rejeitado",
    ]),
    ("2. Política de logs", [
        "tests/test_integration.py::testar_logs_nao_expoem_segredos_nem_conteudo",
        "tests/test_replay.py::testar_repr_do_estado_nao_mostra_segredos",
    ]),
    ("3. Limites: salt 16 B, nonce 12 B, texto 4096 B, clientes concorrentes", [
        "tests/test_server_handshake.py::testar_salt_comum_na_execucao_e_novo_apos_reinicio",
        "tests/test_aead.py::testar_nonce_e_iv_base_seguido_do_seq_big_endian",
        "tests/test_aead.py::testar_texto_de_4096_bytes_e_aceito",
        "tests/test_aead.py::testar_texto_de_4097_bytes_e_rejeitado",
        "tests/test_server_handshake.py::testar_registros_simultaneos_preservam_lista_e_eventos",
    ]),
    ("4. Reconexão com o mesmo client_id", [
        "tests/test_integration.py::testar_reconexao_gera_chaves_novas",
        "tests/test_server_handshake.py::testar_mesma_instancia_renova_chaves_e_rejeita_quadro_antigo",
    ]),
]


def rodar(testes):
    comando = [sys.executable, "-m", "pytest", "-v", "--no-header", "-p", "no:cacheprovider", *testes]
    return subprocess.run(comando, cwd=RAIZ).returncode == 0


def principal():
    resultados = []
    for titulo, testes in GRUPOS:
        print(f"\n{'=' * 78}\n{titulo}\n{'=' * 78}", flush=True)
        resultados.append((titulo, rodar(testes)))

    print(f"\n{'=' * 78}\nRESUMO\n{'=' * 78}")
    for titulo, passou in resultados:
        print(f"  [{'OK' if passou else 'FALHOU'}] {titulo}")
    return 0 if all(passou for _, passou in resultados) else 1


if __name__ == "__main__":
    sys.exit(principal())
