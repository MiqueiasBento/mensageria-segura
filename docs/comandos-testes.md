# Comandos para rodar os testes

## Antes de começar

Abra um PowerShell **na raiz do projeto**, separado das janelas do servidor e dos clientes, e ative o ambiente virtual uma vez:

```powershell
.\.venv\Scripts\Activate.ps1
```

O prompt passa a começar com `(.venv)`. Se aparecer o erro "a execução de scripts foi desabilitada", rode uma vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` e ative de novo.

Sem ativar o ambiente, troque `pytest` por `.\.venv\Scripts\python.exe -m pytest` em qualquer comando abaixo.

## Comandos gerais

```powershell
pytest -v -k "not persistencia"   # todos os testes
pytest -q -k "not persistencia"   # todos, só o resumo
pytest -v -k replay            # todos cujo nome contém "replay"
pytest --collect-only -q       # lista os testes sem rodar
pytest -v -s <teste>           # mostra os print() do teste
```

## Testes mínimos obrigatórios do enunciado

### Tudo de uma vez (script)

```powershell
python -m scripts.testes_obrigatorios
```

Sem o `.venv` ativado: `.\.venv\Scripts\python.exe -m scripts.testes_obrigatorios`.

O script [scripts/testes_obrigatorios.py](../scripts/testes_obrigatorios.py) roda, em blocos separados e com título, os testes de cada item das especificações operacionais do enunciado: troca E2E, bitflip, replay, framing inválido, política de logs, limites (salt, nonce, 4096 bytes, clientes concorrentes) e reconexão. No final mostra um resumo com `[OK]` ou `[FALHOU]` por item.

### Um por um

```powershell
# 2 clientes trocando mensagens E2E
pytest -v tests/test_integration.py::testar_dois_clientes_trocam_mensagens_e2e
pytest -v tests/test_integration.py::testar_so_o_destinatario_recebe_e_decifra

# Bitflip: mensagem adulterada é rejeitada (tag GCM)
pytest -v tests/test_integration.py::testar_bitflip_pela_rede_e_rejeitado
pytest -v tests/test_tampering.py::testar_bit_invertido_em_cada_regiao_e_rejeitado
pytest -v tests/test_aead.py::testar_bit_invertido_no_cifrado_falha_a_tag

# Replay: seq_no repetido é rejeitado
pytest -v tests/test_integration.py::testar_replay_pela_rede_e_rejeitado
pytest -v tests/test_replay.py::testar_reenviar_a_mesma_mensagem_e_replay

# Framing inválido: erro e desconexão segura
pytest -v tests/test_initial_server.py::testar_desconexao_por_quadro_invalido
pytest -v tests/test_framing.py::testar_tamanho_acima_do_limite_e_rejeitado_sem_ler_o_corpo

# Logs sem segredos e reconexão com o mesmo client_id
pytest -v tests/test_integration.py::testar_logs_nao_expoem_segredos_nem_conteudo
pytest -v tests/test_integration.py::testar_reconexao_gera_chaves_novas
```

## Todos os testes, por arquivo

Testes com vários casos (parametrizados) rodam todos os casos quando chamados pelo nome.

### tests/test_aead.py

AES-128-GCM, nonce, AAD e formato do quadro E2E

```powershell
# arquivo inteiro
pytest -v tests/test_aead.py

pytest -v tests/test_aead.py::testar_nonce_e_iv_base_seguido_do_seq_big_endian
pytest -v tests/test_aead.py::testar_seq_diferente_gera_nonce_diferente
pytest -v tests/test_aead.py::testar_aad_e_remetente_destinatario_e_seq
pytest -v tests/test_aead.py::testar_seq_invalido_e_rejeitado
pytest -v tests/test_aead.py::testar_iv_base_e_ids_com_tamanho_errado_sao_rejeitados
pytest -v tests/test_aead.py::testar_ida_e_volta_devolve_o_texto
pytest -v tests/test_aead.py::testar_cifrado_tem_tag_de_16_bytes_e_esconde_o_texto
pytest -v tests/test_aead.py::testar_texto_de_4096_bytes_e_aceito
pytest -v tests/test_aead.py::testar_texto_de_4097_bytes_e_rejeitado
pytest -v tests/test_aead.py::testar_aad_diferente_falha_a_tag
pytest -v tests/test_aead.py::testar_chave_errada_falha_a_tag
pytest -v tests/test_aead.py::testar_nonce_errado_falha_a_tag
pytest -v tests/test_aead.py::testar_bit_invertido_no_cifrado_falha_a_tag
pytest -v tests/test_aead.py::testar_chave_aes_256_e_rejeitada
pytest -v tests/test_aead.py::testar_cifrado_menor_que_a_tag_e_rejeitado
pytest -v tests/test_aead.py::testar_quadro_tem_os_campos_na_ordem_do_enunciado
pytest -v tests/test_aead.py::testar_montar_e_separar_quadro_devolvem_os_mesmos_campos
pytest -v tests/test_aead.py::testar_fluxo_completo_do_remetente_ao_destinatario
pytest -v tests/test_aead.py::testar_trocar_destinatario_no_quadro_falha_a_tag
pytest -v tests/test_aead.py::testar_quadro_minimo_e_maximo_sao_aceitos
pytest -v tests/test_aead.py::testar_quadro_com_tamanho_invalido_e_rejeitado
pytest -v tests/test_aead.py::testar_montar_quadro_rejeita_cifrado_sem_tag
```

### tests/test_client_connection.py

Rede do cliente: registro, lista de peers e erros do servidor

```powershell
# arquivo inteiro
pytest -v tests/test_client_connection.py

pytest -v tests/test_client_connection.py::testar_cliente_registra_recebe_lista_entrada_e_saida
pytest -v tests/test_client_connection.py::testar_receber_mensagem_retorna_none_quando_servidor_fecha
pytest -v tests/test_client_connection.py::testar_quadro_invalido_do_servidor_e_erro_no_cliente
pytest -v tests/test_client_connection.py::testar_registro_rejeita_dados_invalidos_antes_de_enviar
```

### tests/test_framing.py

Framing TCP com prefixo de 4 bytes e quadros inválidos

```powershell
# arquivo inteiro
pytest -v tests/test_framing.py

pytest -v tests/test_framing.py::testar_escrita_usa_prefixo_big_endian_de_4_bytes
pytest -v tests/test_framing.py::testar_ida_e_volta_preserva_o_corpo
pytest -v tests/test_framing.py::testar_varios_quadros_no_mesmo_bloco_tcp
pytest -v tests/test_framing.py::testar_quadro_entregue_byte_a_byte
pytest -v tests/test_framing.py::testar_eof_sem_dados_retorna_none
pytest -v tests/test_framing.py::testar_cabecalho_incompleto_e_rejeitado
pytest -v tests/test_framing.py::testar_corpo_incompleto_e_rejeitado
pytest -v tests/test_framing.py::testar_tamanho_zero_e_rejeitado
pytest -v tests/test_framing.py::testar_tamanho_acima_do_limite_e_rejeitado_sem_ler_o_corpo
pytest -v tests/test_framing.py::testar_tamanho_maximo_e_aceito
pytest -v tests/test_framing.py::testar_escrita_rejeita_corpo_invalido
```

### tests/test_handshake.py

Handshake RSA-PSS, certificado e canal de controle HMAC

```powershell
# arquivo inteiro
pytest -v tests/test_handshake.py -k "not persistencia"

pytest -v tests/test_handshake.py::testar_handshake_e_controle_nos_dois_sentidos
pytest -v tests/test_handshake.py::testar_adulteracao_do_handshake_rejeitada
pytest -v tests/test_handshake.py::testar_certificado_nao_confiavel_rejeitado
pytest -v tests/test_handshake.py::testar_handshake_vincula_identidade_e_chave_do_cliente
pytest -v tests/test_handshake.py::testar_chave_de_ordem_baixa_recusada
pytest -v tests/test_handshake.py::testar_controle_adulterado_nao_avanca_contador
pytest -v tests/test_handshake.py::testar_controle_de_outra_conexao_rejeitado
pytest -v tests/test_handshake.py::testar_certificado_vencido_rejeitado
pytest -v tests/test_handshake.py::testar_chave_incompativel_com_certificado
```

### tests/test_initial_server.py

Servidor: registro, encaminhamento e desconexão por quadro inválido

```powershell
# arquivo inteiro
pytest -v tests/test_initial_server.py

pytest -v tests/test_initial_server.py::testar_registro_encaminhamento_e_desconexao
pytest -v tests/test_initial_server.py::testar_desconexao_por_quadro_invalido
pytest -v tests/test_initial_server.py::testar_leitura_e_tamanho_do_quadro
```

### tests/test_integration.py

Servidor real + clientes: E2E, bitflip, replay, logs e reconexão

```powershell
# arquivo inteiro
pytest -v tests/test_integration.py

pytest -v tests/test_integration.py::testar_dois_clientes_trocam_mensagens_e2e
pytest -v tests/test_integration.py::testar_so_o_destinatario_recebe_e_decifra
pytest -v tests/test_integration.py::testar_replay_pela_rede_e_rejeitado
pytest -v tests/test_integration.py::testar_bitflip_pela_rede_e_rejeitado
pytest -v tests/test_integration.py::testar_reconexao_gera_chaves_novas
pytest -v tests/test_integration.py::testar_cliente_desconecta_com_quadro_invalido_do_servidor
pytest -v tests/test_integration.py::testar_logs_nao_expoem_segredos_nem_conteudo
pytest -v tests/test_integration.py::testar_mensagem_error_do_servidor_nao_derruba_o_cliente
```

### tests/test_key_derivation.py

X25519 (ECDH) e HKDF (Extract/Expand, chaves A2B/B2A)

```powershell
# arquivo inteiro
pytest -v tests/test_key_derivation.py

pytest -v tests/test_key_derivation.py::testar_chave_publica_tem_32_bytes
pytest -v tests/test_key_derivation.py::testar_cada_par_gerado_e_diferente
pytest -v tests/test_key_derivation.py::testar_a_e_b_calculam_o_mesmo_segredo
pytest -v tests/test_key_derivation.py::testar_terceiro_cliente_obtem_segredo_diferente
pytest -v tests/test_key_derivation.py::testar_segredo_nao_depende_so_das_chaves_publicas
pytest -v tests/test_key_derivation.py::testar_chave_publica_com_formato_invalido_e_rejeitada
pytest -v tests/test_key_derivation.py::testar_chave_publica_de_ordem_baixa_e_rejeitada
pytest -v tests/test_key_derivation.py::testar_vetor_rfc5869_caso_1
pytest -v tests/test_key_derivation.py::testar_envio_de_um_lado_e_recebimento_do_outro
pytest -v tests/test_key_derivation.py::testar_direcoes_usam_chaves_diferentes
pytest -v tests/test_key_derivation.py::testar_chaves_tem_16_bytes
pytest -v tests/test_key_derivation.py::testar_menor_id_e_o_lado_a
pytest -v tests/test_key_derivation.py::testar_salt_diferente_gera_chaves_diferentes
pytest -v tests/test_key_derivation.py::testar_salts_diferentes_nos_dois_lados_nao_combinam
pytest -v tests/test_key_derivation.py::testar_pares_diferentes_tem_chaves_diferentes
pytest -v tests/test_key_derivation.py::testar_entradas_com_tamanho_invalido_sao_rejeitadas
pytest -v tests/test_key_derivation.py::testar_id_do_peer_igual_ao_proprio_e_rejeitado
```

### tests/test_replay.py

Contadores seq_no e proteção contra replay

```powershell
# arquivo inteiro
pytest -v tests/test_replay.py

pytest -v tests/test_replay.py::testar_estados_dos_dois_lados_tem_chaves_cruzadas
pytest -v tests/test_replay.py::testar_repr_do_estado_nao_mostra_segredos
pytest -v tests/test_replay.py::testar_tres_mensagens_aceitas_em_ordem
pytest -v tests/test_replay.py::testar_conversa_nos_dois_sentidos_usa_contadores_independentes
pytest -v tests/test_replay.py::testar_reenviar_a_mesma_mensagem_e_replay
pytest -v tests/test_replay.py::testar_reenviar_a_primeira_depois_da_terceira_e_replay
pytest -v tests/test_replay.py::testar_seq_pode_pular_mas_nao_voltar
pytest -v tests/test_replay.py::testar_quadro_com_tag_invalida_nao_avanca_o_contador
pytest -v tests/test_replay.py::testar_seq_forjado_muito_alto_nao_trava_a_conversa
pytest -v tests/test_replay.py::testar_iv_base_fica_fixo_apos_o_primeiro_quadro
pytest -v tests/test_replay.py::testar_falha_ao_cifrar_nao_consome_o_seq
pytest -v tests/test_replay.py::testar_contador_de_envio_esgotado_e_rejeitado
```

### tests/test_server_handshake.py

Handshake pela rede, sessões, salt e concorrência

```powershell
# arquivo inteiro
pytest -v tests/test_server_handshake.py

pytest -v tests/test_server_handshake.py::testar_certificado_errado_impede_registro
pytest -v tests/test_server_handshake.py::testar_handshake_adulterado_na_rede_fecha_cliente
pytest -v tests/test_server_handshake.py::testar_registro_nao_aparece_antes_da_prova_de_posse
pytest -v tests/test_server_handshake.py::testar_lista_de_chaves_adulterada_apos_mac_e_recusada
pytest -v tests/test_server_handshake.py::testar_replay_administrativo_do_servidor_desconecta
pytest -v tests/test_server_handshake.py::testar_replay_de_comando_do_cliente_fecha_apenas_sua_conexao
pytest -v tests/test_server_handshake.py::testar_mesma_instancia_renova_chaves_e_rejeita_quadro_antigo
pytest -v tests/test_server_handshake.py::testar_salt_comum_na_execucao_e_novo_apos_reinicio
pytest -v tests/test_server_handshake.py::testar_id_duplicado_preserva_sessao_original
pytest -v tests/test_server_handshake.py::testar_handshake_abandonado_expira
pytest -v tests/test_server_handshake.py::testar_registros_simultaneos_preservam_lista_e_eventos
pytest -v tests/test_server_handshake.py::testar_falha_de_escrita_no_destino_preserva_remetente
```

### tests/test_tampering.py

Adulteração (bitflip) em cada região do quadro E2E

```powershell
# arquivo inteiro
pytest -v tests/test_tampering.py

pytest -v tests/test_tampering.py::testar_bit_invertido_em_cada_regiao_e_rejeitado
pytest -v tests/test_tampering.py::testar_quadro_destinado_a_outro_cliente_e_rejeitado
pytest -v tests/test_tampering.py::testar_quadro_de_outro_remetente_e_rejeitado
pytest -v tests/test_tampering.py::testar_remetente_falsificado_sem_a_chave_e_rejeitado
pytest -v tests/test_tampering.py::testar_quadro_malformado_e_rejeitado
```

