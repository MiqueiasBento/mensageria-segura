# Plano de testes e aceitação

Execução de referência em 03/11/2026: **149 testes aprovados** com Python 3.12.3. Os testes de rede precisam de permissão para abrir sockets TCP locais. Eles geram um certificado temporário confiável por fixture; a aplicação normal exige provisionamento explícito.

## Executar

Na raiz do repositório:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -v tests/test_handshake.py tests/test_server_handshake.py
.venv/bin/python -m pytest -v tests/test_tampering.py tests/test_replay.py tests/test_integration.py
```

## Critérios de aceitação e evidência

| Critério | Evidência | Estado |
| --- | --- | --- |
| Dois ou mais clientes conectados e troca nos dois sentidos | `test_integration.py`, `test_server_handshake.py` e demonstração com três processos | Atendido |
| Framing de quatro bytes e rejeição de limites/truncamentos | `test_framing.py`, `test_initial_server.py` | Atendido |
| Registro, lista, entrada e remoção de clientes | `test_initial_server.py`, `test_client_connection.py` | Atendido |
| Registro só após prova de posse da chave efêmera | `testar_registro_nao_aparece_antes_da_prova_de_posse` | Atendido |
| Certificado não confiável e assinatura inválida recusados | `test_handshake.py`, `test_server_handshake.py` | Atendido |
| Certificado vencido recusado e chave privada correspondente | `test_handshake.py` | Atendido |
| Lista de chaves autenticada e controle protegido contra replay | `testar_lista_de_chaves_adulterada_apos_mac_e_recusada` e testes de replay administrativo | Atendido |
| X25519/HKDF produz chaves direcionais compatíveis | `test_key_derivation.py`, incluindo vetor RFC 5869 | Atendido |
| AES-128-GCM com nonce, AAD e limite de 4096 bytes | `test_aead.py` | Atendido |
| Alteração de conteúdo, IDs, sequência, nonce ou tag rejeitada | `test_tampering.py`, `test_integration.py` | Atendido |
| Replay E2E rejeitado sem avançar estado em falha de tag | `test_replay.py`, `test_integration.py` | Atendido |
| Reconexão gera novas chaves, inclusive na mesma instância | `test_integration.py`, `testar_mesma_instancia_renova_chaves_e_rejeita_quadro_antigo` | Atendido |
| Destino ausente ou falha de escrita não derruba remetente | `testar_mensagem_error_do_servidor_nao_derruba_o_cliente`, `testar_falha_de_escrita_no_destino_preserva_remetente` | Atendido |
| ID duplicado não substitui sessão existente | `testar_id_duplicado_preserva_sessao_original` | Atendido |
| Registros simultâneos preservam listas e eventos | `testar_registros_simultaneos_preservam_lista_e_eventos` | Atendido |
| Conexão sem concluir handshake expira | `testar_handshake_abandonado_expira` | Atendido |
| Logs não expõem conteúdo ou chaves das conversas | `testar_logs_nao_expoem_segredos_nem_conteudo` e demonstração CLI | Atendido nos cenários executados |
| Geração reproduzível sem sobrescrever identidade | `testar_persistencia_identidade_permissoes_e_nao_sobrescrita` e execução real do gerador | Atendido |

## Demonstração manual

1. Prepare o ambiente e gere a identidade conforme o [README](../README.md).
2. Abra o servidor e dois clientes em três terminais.
3. Execute `/peers` em cada cliente e mostre os UUIDs.
4. Envie mensagens nos dois sentidos com `/msg`.
5. Observe que o servidor mostra origem, destino e tamanho; o texto aparece somente nos clientes.
6. Saia de um cliente com `/sair` e observe a remoção no outro.
7. Abra esse cliente novamente e observe um novo registro e uma nova chave pública.
8. Execute os testes de assinatura, adulteração e replay com `pytest -v` para apresentar as rejeições.
9. Pare o servidor com `Ctrl+C`.

A execução automatizada da interface com três processos reais confirmou conexão autenticada, `/peers`, mensagens nos dois sentidos, `/sair`, logs e encerramento do servidor sem traceback.

## Limites da evidência

Os testes cobrem os requisitos transcritos no repositório e os cenários descritos acima. Eles não são uma auditoria criptográfica formal, um teste de carga nem uma comprovação de resistência a servidor comprometido. O modelo de confiança do diretório está em [protocol.md](protocol.md).

A dupla ainda deve ensaiar a apresentação e explicar as decisões com suas próprias palavras. Essa verificação humana não pode ser marcada como concluída por testes de software.
