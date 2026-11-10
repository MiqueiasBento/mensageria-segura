# Roteiro curto de apresentação — Dev B

**Atividades realizadas:**

- Cliente TCP e interface de terminal
- Troca de chaves X25519 (ECDH) e derivação HKDF das chaves de cada direção
- Cifragem AES-128-GCM, montagem do nonce e do quadro E2E
- Contadores `seq_no`, proteção contra replay e testes de adulteração

**Objetivo:** apresentar sua parte em cerca de 5 a 7 minutos, logo depois do Dev A. As falas abaixo já fazem a transição entre os arquivos.

Abra **quatro arquivos principais**: `src/crypto/key_derivation.py`, `src/crypto/aead.py`, `src/client/peers.py` e `src/client/messaging.py`. Deixe `src/common/constants.py`, `src/client/main.py`, `tests/test_tampering.py` e `tests/test_integration.py` em abas, para mostrar se houver tempo ou pergunta.

**Ordem para lembrar:** gerar chave efêmera → calcular segredo Z → derivar chaves A2B/B2A → cifrar com nonce e AAD → receber: checar seq, checar tag, só então aceitar.

O Dev A já explicou o servidor, o handshake RSA-PSS e o relay. Você começa no ponto em que o cliente **já recebeu a chave pública do outro cliente**.

---

## 1. Transição e visão geral — cerca de 30 segundos

**Mostre:** o slide "Como funciona", passos 6 e 7.

**Fale:**

> "O Dev A mostrou como o servidor autentica a conexão e entrega a lista de chaves públicas. A minha parte começa aí: o que o cliente faz com essas chaves para conversar com outro cliente sem que o servidor consiga ler.
>
> São três etapas: primeiro os dois clientes chegam ao mesmo segredo sem enviá-lo pela rede; depois transformam esse segredo em chaves AES; e por último cada mensagem é cifrada e numerada, para que adulteração e repetição sejam detectadas."

---

## 2. Chave efêmera e segredo compartilhado — cerca de 1 minuto

**Mostre:** `crypto/key_derivation.py`, `gerar_par_efemero` (linhas 13–17) e `calcular_segredo` (linhas 20–25).

**Fale:**

> "[Aponte `gerar_par_efemero`.] Cada vez que o cliente conecta, ele gera um par de chaves X25519 novo. A chave pública tem 32 bytes e vai para o servidor no REGISTER. A privada fica só na memória do cliente; ela nunca é enviada e nunca aparece em log.
>
> [Aponte `calcular_segredo`.] Quando Alice recebe a chave pública do Bob, ela faz o ECDH: combina a privada dela com a pública dele. O Bob faz o mesmo com a privada dele e a pública da Alice. Pela matemática da curva, os dois chegam ao **mesmo valor Z**, de 32 bytes, e esse Z nunca passou pela rede. O servidor só viu as chaves públicas, e com elas não dá para calcular Z.
>
> Como as chaves são descartadas ao desconectar, temos sigilo perfeito: mesmo que a chave RSA do servidor vaze no futuro, conversas antigas continuam protegidas."

**Se perguntarem "e se mandarem uma chave pública inválida?":** "A biblioteca rejeita chaves de ordem baixa, que dariam um Z só com zeros. O cliente trata como erro de protocolo." (comentário na linha 24; teste `testar_chave_publica_de_ordem_baixa_e_rejeitada`).

---

## 3. Derivação das chaves com HKDF — cerca de 1 minuto

**Mostre:** `crypto/key_derivation.py`, `hkdf_extract`, `hkdf_expand` e `derivar_chaves` (linhas 28–61).

**Fale:**

> "Z não é usado direto como chave AES. Passamos ele pelo HKDF com SHA-256, em duas etapas.
>
> [Aponte `hkdf_extract`.] O *Extract* mistura Z com o salt de 16 bytes que o servidor enviou no handshake e gera uma chave intermediária, o PRK.
>
> [Aponte `hkdf_expand`.] O *Expand* gera, a partir do PRK, duas chaves de 16 bytes com rótulos diferentes: `A2B` e `B2A`. Então cada direção da conversa tem sua própria chave.
>
> [Aponte o final de `derivar_chaves`.] Para os dois lados concordarem sobre quem é o 'A', usamos uma regra fixa: o cliente com o **menor UUID em bytes** é o A. Assim a Alice usa A2B para enviar e o Bob usa A2B para receber, sem precisar trocar nenhuma mensagem extra."

**Se perguntarem "por que duas chaves?":** "Para que as duas direções nunca usem a mesma combinação de chave e nonce. Se usassem a mesma chave, um contador igual nos dois sentidos repetiria o nonce, o que quebra o GCM."

---

## 4. Cifragem e formato da mensagem — cerca de 1 minuto e 30 segundos

**Mostre:** `crypto/aead.py`, `montar_nonce`, `montar_aad` e `cifrar` (linhas 37–54); depois `montar_quadro_e2e` (linhas 66–70). Em seguida `client/peers.py`, `EstadoPeer` (linhas 29–39) e `preparar_envio` (linhas 48–57).

**Fale:**

> "Para cifrar usamos AES-128-GCM. É um modo AEAD: ele cifra e, junto, gera uma **tag de 16 bytes** que funciona como um selo. Se qualquer bit for alterado, a tag não confere.
>
> [Aponte `montar_nonce`.] O GCM exige um nonce de 12 bytes que nunca se repita com a mesma chave. Montamos com 4 bytes aleatórios por sessão, o IV base, mais os 8 bytes do número de sequência. Como o contador só cresce, o nonce nunca se repete.
>
> [Aponte `montar_aad`.] O AAD são dados que não são cifrados, mas entram no cálculo da tag: remetente, destinatário e número de sequência. Então ninguém consegue trocar o destinatário ou o contador sem invalidar a mensagem.
>
> [Aponte `montar_quadro_e2e`.] O quadro final segue a ordem do enunciado: nonce, sender_id, recipient_id, seq_no e, no fim, o texto cifrado com a tag.
>
> [Em `peers.py`, aponte `EstadoPeer`.] Para cada contato o cliente guarda uma estrutura com as duas chaves, os dois contadores e os IV bases. É a tabela `peers` do enunciado. As chaves estão marcadas com `repr=False`, para não aparecerem se alguém imprimir o objeto.
>
> [Aponte `preparar_envio`.] Ao enviar: pega o contador, monta o nonce, cifra com o AAD, monta o quadro e **só então** incrementa o contador. Esse quadro vai como payload do RELAY, que o Dev A mostrou: o servidor só repassa."

---

## 5. Recebimento e proteção contra ataques — cerca de 1 minuto e 30 segundos

**Mostre:** `client/peers.py`, `processar_recebimento` (linhas 60–88). Depois, se houver tempo, `client/messaging.py`, `_receber_relay` (linhas 206–227).

**Fale:**

> "Esta é a função mais importante da minha parte, porque é onde os ataques são barrados. As verificações seguem uma ordem:
>
> [Aponte linhas 66–69.] Primeiro confere se o quadro veio de quem diz e se é para mim.
>
> [Aponte linha 70.] Depois o **replay**: se o número de sequência for menor ou igual ao último aceito, a mensagem é rejeitada. Se alguém gravar uma mensagem válida e reenviar, ela é descartada.
>
> [Aponte linhas 73–77.] Confere se o nonce bate com o número de sequência e se o IV base é o mesmo do primeiro quadro.
>
> [Aponte linhas 79–82.] Aí decifra. Se a tag falhar, que é o caso do **bitflip**, a mensagem é rejeitada.
>
> [Aponte linhas 84–87.] Só depois de tudo validado o contador avança. Isso é proposital: se o contador avançasse antes, um atacante poderia mandar um quadro falso com contador altíssimo e travar a conversa. Assim, um quadro forjado não muda nada no estado."

**Se mostrar `_receber_relay`:**

> "Aqui tem uma checagem extra: o servidor informa no JSON quem é o remetente, mas o remetente verdadeiro está dentro do quadro, protegido pela tag. Se os dois não baterem, a mensagem é rejeitada. Então nem o servidor consegue fingir que uma mensagem veio de outra pessoa."

---

## 6. Demonstração dos ataques com testes — cerca de 1 minuto

O Dev A já fez a demonstração em três terminais. A sua parte é mostrar **os ataques sendo rejeitados**.

Prepare antes, num PowerShell novo na raiz do projeto:

```powershell
.\.venv\Scripts\Activate.ps1
```

Rode, um de cada vez:

```powershell
pytest -v -k bitflip_pela_rede
pytest -v -k replay_pela_rede
pytest -v -k bit_invertido_em_cada_regiao
```

**Fale enquanto roda:**

> "Estes testes sobem um servidor real e dois clientes. No primeiro, um relay malicioso inverte um bit da mensagem no caminho: em cada uma das seis regiões do quadro, o Bob rejeita, o contador dele continua em -1 e a próxima mensagem legítima é aceita normalmente.
>
> No segundo, o relay entrega a mesma mensagem duas vezes. A primeira é aceita, a segunda é rejeitada com motivo replay, e a conversa continua.
>
> O terceiro inverte o primeiro e o último bit de cada parte do quadro, sem rede: nonce, IDs, contador, texto cifrado e tag. Todos são rejeitados."

**Se pedirem para abrir o teste:** `tests/test_integration.py`, `testar_bitflip_pela_rede_e_rejeitado` (linha 119) e `testar_replay_pela_rede_e_rejeitado` (linha 103). O relay malicioso é simulado pela função `interceptar_relay`.

**Plano B:** se o `Activate.ps1` falhar, use `.\.venv\Scripts\python.exe -m pytest -v -k bitflip_pela_rede`.

---

## 7. Encerramento — cerca de 20 segundos

**Fale:**

> "Resumindo a minha parte: cada cliente gera chaves novas a cada conexão, chega ao mesmo segredo que o outro sem enviá-lo, deriva uma chave para cada direção e cifra cada mensagem com AES-GCM, nonce único e contador. Adulteração é pega pela tag, repetição é pega pelo contador, e o servidor transporta tudo sem conseguir ler. Juntando com a parte do Dev A, temos as quatro garantias: confidencialidade, integridade, autenticidade e sigilo perfeito."

---

## Testes mínimos do enunciado: o que é da sua parte

| Critério | Onde abrir | O que o teste verifica |
| --- | --- | --- |
| Bitflip | `test_integration.py`, `testar_bitflip_pela_rede_e_rejeitado`; `test_tampering.py`, `testar_bit_invertido_em_cada_regiao_e_rejeitado`; `test_aead.py`, `testar_bit_invertido_no_cifrado_falha_a_tag` | Um bit invertido em qualquer região é rejeitado, o contador não avança e a mensagem seguinte é aceita. O teste de `test_aead.py` confirma especificamente o `InvalidTag` do AES-GCM. |
| Replay | `test_integration.py`, `testar_replay_pela_rede_e_rejeitado`; `test_replay.py`, `testar_reenviar_a_mesma_mensagem_e_replay` e `testar_reenviar_a_primeira_depois_da_terceira_e_replay` | Mesmo quadro duas vezes ou quadro antigo depois de um novo: rejeitado com motivo replay. |
| Quadro forjado não trava a conversa | `test_replay.py`, `testar_quadro_com_tag_invalida_nao_avanca_o_contador` e `testar_seq_forjado_muito_alto_nao_trava_a_conversa` | Um quadro com tag inválida ou contador forjado não altera o estado do receptor. |
| Nonce de 12 bytes | `test_aead.py`, `testar_nonce_e_iv_base_seguido_do_seq_big_endian` | O nonce é IV base de 4 bytes seguido do contador de 8 bytes em big-endian. |
| Texto até 4096 bytes | `test_aead.py`, `testar_texto_de_4096_bytes_e_aceito` e `testar_texto_de_4097_bytes_e_rejeitado` | O limite é em bytes; letras acentuadas usam mais de um byte em UTF-8. |
| Chaves por direção | `test_key_derivation.py`, `testar_direcoes_usam_chaves_diferentes` e `testar_menor_id_e_o_lado_a` | A2B ≠ B2A, e os dois lados concordam sobre quem é o A. |
| HKDF correto | `test_key_derivation.py`, `testar_vetor_rfc5869_caso_1` | A implementação reproduz o vetor de teste oficial da RFC 5869. |

---

## Cola de última hora

- **X25519:** cada lado combina a própria privada com a pública do outro; os dois chegam ao mesmo Z sem enviá-lo.
- **Efêmera:** chave nova a cada conexão → sigilo perfeito.
- **HKDF:** Extract (Z + salt → PRK) e Expand (PRK + rótulo → chave de 16 bytes). Rótulos `A2B` e `B2A`.
- **Quem é A:** o cliente de menor UUID em bytes.
- **AES-128-GCM:** cifra e gera tag de 16 bytes; qualquer bit alterado invalida a tag.
- **Nonce:** IV base (4B, aleatório) ‖ seq_no (8B). Nunca se repete com a mesma chave.
- **AAD:** sender_id ‖ recipient_id ‖ seq_no. Não é cifrado, mas é autenticado.
- **Quadro:** nonce 12 | sender 16 | recipient 16 | seq 8 | cifrado + tag 16 → no máximo 4164 bytes.
- **Replay:** seq ≤ último aceito → rejeita.
- **Ordem no recebimento:** IDs → seq → nonce/IV → tag → só então avança o contador.
- **Divisão:** o handshake RSA-PSS e o canal HMAC são da parte do Dev A; se perguntarem, diga que o cliente usa `validar_handshake` antes de aceitar a lista de chaves.
