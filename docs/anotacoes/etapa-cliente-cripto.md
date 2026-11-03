## Registro da implementação — cliente e criptografia E2E (Integrante B) — 03/11/2026

Branch `feature/cliente-cripto`. Etapas 1–9 e 11 do passo a passo do Integrante B concluídas;
a Etapa 10 (integração com o handshake) depende do Integrante A e está descrita abaixo.
O servidor **não foi alterado** nesta branch.

### O que foi entregue

| Arquivo | Responsabilidade |
| --- | --- |
| `src/common/constants.py` | Tamanhos fixos do protocolo (ID 16, pk 32, salt 16, nonce 12, IV_base 4, seq 8, tag 16, AES 16, texto ≤ 4096). |
| `src/crypto/key_derivation.py` | Par efêmero X25519, `Z = ECDH(sk, pk_peer)`, HKDF-Extract (HMAC-SHA256) e dois HKDF-Expand (`A2B`, `B2A`, 16 bytes). |
| `src/crypto/aead.py` | AES-128-GCM, nonce `IV_base ‖ seq_no`, AAD `sender_id ‖ recipient_id ‖ seq_no`, montar/separar o quadro E2E. |
| `src/client/peers.py` | Estado por peer (chaves, `seq_envio`, `seq_recebimento`, IV bases) e regras de envio/recebimento anti-replay. |
| `src/client/connection.py` | Rede do cliente: `conectar`, `registrar`, `receber_mensagem`, `enviar_relay`, `fechar`. |
| `src/client/messaging.py` | Classe `Cliente`: junta rede e cripto, mantém `peers`, publica eventos (`entrou`, `saiu`, `mensagem`, `rejeitada`, `desconectado`). |
| `src/client/main.py` | Chat de terminal (`python -m src.client.main`). |

Suíte: `python -m pytest -q` → **117 passed** (estável em execuções repetidas). Demo manual com
servidor + 2 clientes em processos separados verificada: troca de mensagens nos dois sentidos,
entrada/saída de peers, servidor caindo (cliente encerra sozinho) e servidor ausente.

### Decisões que afetam o Integrante A

| # | Decisão | Onde |
| --- | --- | --- |
| 1 | `RELAY.payload` = quadro E2E binário em Base64, no máximo 12+16+16+8+4096+16 = **4164 bytes**. O servidor não deve validar nada além do tamanho (já é assim). | `peers.preparar_envio` |
| 2 | "A" do par = cliente com **menor `client_id` em bytes** (`uuid.UUID(texto).bytes`). Ele envia com `Key_A2B` e recebe com `Key_B2A`. | `key_derivation.derivar_chaves` |
| 3 | O `sender_id` posto pelo servidor no JSON precisa coincidir com o `sender_id` autenticado dentro do quadro; senão a mensagem é rejeitada. | `Cliente._receber_relay` |
| 4 | O receptor aprende o `IV_base` do remetente no primeiro quadro válido e confere nos seguintes; o contador de recebimento só avança depois de a tag GCM ser validada. | `peers.processar_recebimento` |
| 5 | Reconectar = novo `Cliente` = novo par X25519, novas chaves e contadores zerados. Ao receber `CLIENT_LEFT` o estado do peer é apagado; um `CLIENT_JOINED` sempre recria o estado. | `messaging.py` |
| 6 | Renomeado `tests/test_temparing.py` → `tests/test_tampering.py`. | — |

### Etapa 10 — o que falta para integrar o handshake

O ponto de integração no cliente é **um único método**, `Cliente._handshake()` em
`src/client/messaging.py`. Ele é chamado logo depois do `REGISTER` e **antes** de ler o
`CLIENT_LIST`; hoje apenas retorna `SALT_PROVISORIO`.

```python
async def _handshake(self):
    # 1. mensagem = await connection.receber_mensagem(self._leitor)   # resposta do servidor
    # 2. validar certificado contra certs/server.crt (pinado)
    # 3. validar RSA-PSS sobre SHA256(pk_server || pk_client || client_id || salt)
    # 4. se falhar: raise ErroCliente(...)  -> conectar() fecha a conexão
    # 5. return salt_srv (16 bytes)
```

Para isso funcionar, falta combinar:

1. **Formato da resposta** (sugestão: nova mensagem `{"type": "HANDSHAKE", "server_public_key", "certificate", "signature", "salt"}` com binários em Base64, enviada pelo servidor entre o `REGISTER` e o `CLIENT_LIST`).
2. **Mesmo salt para os dois lados de cada par.** Sugestão: um `salt_srv` aleatório por execução do servidor, igual para todos os clientes. Se cada cliente receber um salt diferente, as chaves do par não batem.
3. Quem escreve a verificação (`crypto/handshake.py` / `crypto/identity.py`) e o teste "certificado ou assinatura inválidos → cliente recusa" (`tests/test_handshake.py`). Depois disso, remover `SALT_PROVISORIO` de `key_derivation.py` e dos testes.

### Pontos observados no servidor (sugestões, não alterados)

- **Relay para destinatário desconhecido derruba o remetente.** Se B sair e A enviar antes de receber `CLIENT_LEFT` (condição de corrida), `relay.encaminhar` lança `ErroProtocolo` e o servidor fecha a conexão de A. Sugestão: responder `{"type": "ERROR", "code": "UNKNOWN_CLIENT"}` e manter a conexão. O cliente só envia para peers conhecidos, o que reduz mas não elimina o caso; ele já aceita `{"type": "ERROR", "code": ...}` sem desconectar e mostra o código na tela.
- **Log do relay:** o roteiro de demo prevê o servidor mostrando apenas remetente, destinatário e tamanho de cada quadro encaminhado. Hoje o relay não registra nada.
- Mensagens administrativas do servidor com `seq_send` (citadas no enunciado) continuam pendentes.
