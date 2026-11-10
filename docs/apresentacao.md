# Sistema de Mensageria Segura Multi-Cliente — Guia de apresentação

**Trabalho Prático 3** · Segurança da Informação · Prof. Michel Sales
**Dupla:** Rewelli Oliveira e Miqueias Bento

Este documento reúne a arquitetura, o fluxo do protocolo e o roteiro da apresentação. As falas detalhadas de cada integrante estão nos roteiros individuais; os comandos de teste estão em [comandos-testes.md](comandos-testes.md).

---

## 1. Ideia geral

Um chat de terminal em que dois ou mais clientes conversam com **criptografia ponta a ponta (E2E)**. O servidor fica no meio: autentica as conexões, mantém a lista de clientes online, distribui as chaves públicas e encaminha as mensagens, **sem conseguir decifrá-las**.

```
   Cliente A                     Servidor                      Cliente B
 ┌───────────┐  controle (HMAC) ┌──────────┐ controle (HMAC)  ┌───────────┐
 │ chave E2E │◄────────────────►│  relay   │◄────────────────►│ chave E2E │
 │  A ⇄ B    │  quadro E2E ────►│ (não lê) │──── quadro E2E ►│  A ⇄ B    │
 └───────────┘                  └──────────┘                  └───────────┘
   certificado pinado         chave RSA + certificado         certificado pinado
```

**Garantias pedidas pelo enunciado:**

| Garantia | Mecanismo |
| --- | --- |
| Confidencialidade | AES-128-GCM |
| Integridade | Tag de 16 bytes do AES-GCM |
| Autenticidade do servidor | Assinatura RSA-PSS + certificado pinado |
| Sigilo perfeito (forward secrecy) | Chaves efêmeras X25519 (ECDHE) |
| Anti-replay | `seq_no` monotônico |

---

## 2. Arquitetura do código

O código em `src/` tem quatro pastas, cada uma com uma responsabilidade.

| Pasta | Responsabilidade | Quem implementou |
| --- | --- | --- |
| `common/` | Base compartilhada: tamanhos, framing TCP, JSON | Ambos |
| `crypto/` | Funções criptográficas puras, sem rede | Dev A: identidade e handshake · Dev B: ECDH, HKDF, AES-GCM |
| `server/` | Servidor: handshake, sessões, diretório, relay | Dev A (Miqueias) |
| `client/` | Cliente: conexão, estado por peer, E2E, terminal | Dev B (Rewelli) |

### Arquivos

| Arquivo | O que faz | Funções principais |
| --- | --- | --- |
| `common/constants.py` | Tamanhos fixos do protocolo (ID 16, chave 32, salt 16, nonce 12, tag 16, texto ≤ 4096) | — |
| `common/framing.py` | Prefixo de 4 bytes com o tamanho de cada mensagem TCP; rejeita tamanho 0, > 64 KiB ou incompleto | `ler_quadro`, `escrever_quadro` |
| `common/protocol.py` | Codifica/decodifica JSON e valida UUID, chave pública e payload | `codificar_mensagem`, `decodificar_mensagem`, `validar_id_cliente` |
| `crypto/identity.py` | Chave RSA 3072 bits e certificado autoassinado do servidor | `gerar_identidade`, `carregar_identidade`, `validar_certificado` |
| `crypto/handshake.py` | Assina e verifica o handshake (RSA-PSS); canal de controle com HMAC | `criar_handshake`, `validar_handshake`, `CanalAutenticado` |
| `crypto/key_derivation.py` | Par X25519, segredo ECDH e HKDF (Extract + Expand) | `gerar_par_efemero`, `calcular_segredo`, `derivar_chaves` |
| `crypto/aead.py` | AES-128-GCM, nonce, AAD e quadro E2E | `cifrar`, `decifrar`, `montar_quadro_e2e`, `separar_quadro_e2e` |
| `server/main.py` | Carrega a identidade, gera o salt, abre a porta TCP | `iniciar_servidor`, `executar` |
| `server/connection.py` | Ciclo de cada cliente: handshake → registro → relay → saída | `atender_cliente`, `enviar`, `avisar` |
| `server/sessions.py` | Tabela `sessions`: UUID, chave pública, conexão, canal; limite de 128 | `RegistroSessoes` |
| `server/relay.py` | Encaminha o payload cifrado sem abrir; loga só origem, destino e tamanho | `encaminhar` |
| `client/connection.py` | Rede do cliente: TCP, REGISTER, RELAY | `registrar`, `receber_mensagem`, `enviar_relay` |
| `client/peers.py` | Tabela `peers`: chaves por direção, contadores, IV; regras anti-replay | `preparar_envio`, `processar_recebimento` |
| `client/messaging.py` | Classe `Cliente`: junta rede e criptografia, gera eventos | `conectar`, `enviar_texto`, `escutar` |
| `client/main.py` | Interface de terminal: `/peers`, `/msg`, `/id`, `/sair` | `executar_comando`, `mostrar_eventos` |

---

## 3. Fluxo do protocolo

### Fase 1 — Registro (handshake)

```
Cliente A                                   Servidor
   │ gera par X25519 (sk_A, pk_A)              │
   │── 1. REGISTER {client_id, pk_A} ────────► │
   │                                           │ gera par X25519 próprio
   │                                           │ assina SHA256(pk_S‖pk_A‖id‖salt) com RSA-PSS
   │◄─ 2. HANDSHAKE {pk_S, cert, assinatura, salt}
   │ 3. certificado == pinado?                 │
   │    assinatura válida?  → senão desconecta │
   │── READY (com HMAC) ─────────────────────► │
   │                                           │ só agora registra A na tabela sessions
   │◄─ CLIENT_LIST (clientes já online) ─────  │
```

1. **REGISTER:** A gera um par de chaves efêmero e envia seu UUID e a chave pública.
2. **HANDSHAKE:** o servidor responde com sua chave efêmera, o certificado, o salt e uma assinatura RSA-PSS sobre esses dados.
3. **Validação:** A confere o certificado com a cópia pinada e verifica a assinatura. Isso impede *man-in-the-middle*. Depois envia `READY`, provando que tem a chave privada.
4. **B faz o mesmo.**
5. **Distribuição:** B recebe `CLIENT_LIST` com pk_A; A recebe `CLIENT_JOINED` com pk_B. Mensagens de controle vão protegidas por HMAC.

### Fase 2 — Conversa (E2E)

```
Cliente A                         Servidor                         Cliente B
Z = ECDH(sk_A, pk_B)        (só viu chaves públicas)        Z = ECDH(sk_B, pk_A)
HKDF(salt, Z) → Key_A2B, Key_B2A                    HKDF(salt, Z) → Key_A2B, Key_B2A
   │                                 │                                 │
   │ cifra com Key_A2B, seq_no = n   │                                 │
   │── RELAY {para B, quadro E2E} ─► │── RELAY {de A, quadro E2E} ───► │
   │                                 │  (repassa sem abrir)            │ seq_no novo?
   │                                 │                                 │ tag válida?
   │                                 │                                 │ → decifra
```

6. **Segredo compartilhado:** cada lado combina a própria privada com a pública do outro e os dois chegam ao **mesmo Z**, que nunca passa pela rede. O HKDF transforma Z em duas chaves AES de 16 bytes, uma para cada direção. O cliente de menor UUID é o "A".
7. **Mensagem:** A cifra com AES-128-GCM, o servidor repassa sem abrir e B valida o contador e a tag antes de decifrar.

### Saída

Ao desconectar, o servidor remove a sessão e avisa os outros com `CLIENT_LEFT`. Ao reconectar, o cliente gera um par novo, faz o handshake completo e deriva chaves novas, com contadores zerados.

---

## 4. Quadro E2E

O pacote binário de cada mensagem entre clientes, no formato do enunciado:

```
┌──────────┬────────────┬───────────────┬──────────┬─────────────────────┐
│ nonce    │ sender_id  │ recipient_id  │ seq_no   │ texto cifrado + tag │
│ 12 bytes │ 16 bytes   │ 16 bytes      │ 8 bytes  │ até 4096 + 16 bytes │
└──────────┴────────────┴───────────────┴──────────┴─────────────────────┘
```

- **nonce** = `IV_base (4 bytes aleatórios) ‖ seq_no (8 bytes)`. Nunca se repete com a mesma chave.
- **AAD** = `sender_id ‖ recipient_id ‖ seq_no`. Não é cifrado, mas entra na tag: alterar qualquer um invalida a mensagem.
- Tamanho máximo: **4164 bytes**.

Ele viaja como `payload` (Base64) dentro de uma mensagem `RELAY`, que vai dentro de um envelope `AUTH` com HMAC, que vai dentro de um quadro TCP com prefixo de tamanho. O servidor abre as camadas externas, mas apenas repassa o quadro E2E.

---

## 5. Algoritmos

| Algoritmo | Problema que resolve | Onde |
| --- | --- | --- |
| **X25519 (ECDHE)** | Combinar um segredo sem enviá-lo; chaves novas a cada conexão dão sigilo perfeito | `crypto/key_derivation.py` |
| **HKDF-SHA256** | Transformar o Z bruto em chaves AES uniformes: Extract (Z + salt → PRK) e Expand (PRK + "A2B"/"B2A" → 16 bytes) | `crypto/key_derivation.py` |
| **AES-128-GCM** | Cifrar e detectar qualquer alteração (tag de 16 bytes) | `crypto/aead.py` |
| **RSA-PSS + SHA-256** | Provar que a resposta veio do servidor verdadeiro | `crypto/handshake.py` |
| **HMAC-SHA256** | Autenticar mensagens de controle (lista de clientes, entradas, saídas) | `crypto/handshake.py` |
| **`seq_no` monotônico** | Rejeitar mensagens repetidas (replay) | `client/peers.py` |

---

## 6. Estruturas de dados

**Servidor — tabela `sessions`** (`server/sessions.py`)

| Campo | Conteúdo |
| --- | --- |
| `id_cliente` | UUID do cliente |
| `chave_publica` | pk X25519 do cliente |
| `escritor` | Conexão TCP |
| `canal` | Chaves HMAC e contadores `seq_send` / `seq_recv` do controle |

O servidor **não** guarda nenhuma chave AES da conversa.

**Cliente — tabela `peers`** (`client/peers.py`, classe `EstadoPeer`)

| Campo | Conteúdo |
| --- | --- |
| `chave_publica` | pk X25519 do peer |
| `chave_envio` / `chave_recebimento` | Key_A2B / Key_B2A |
| `seq_envio` | Próximo contador a enviar (começa em 0) |
| `seq_recebimento` | Último contador aceito (começa em -1) |
| `iv_base_envio` / `iv_base_recebimento` | IV base de cada direção |

---

## 7. Proteções contra ataques

| Ataque | Defesa | Onde no código |
| --- | --- | --- |
| Servidor impostor / MITM no handshake | Certificado pinado + assinatura RSA-PSS | `crypto/handshake.py`, `validar_handshake` |
| Adulteração (bitflip) | Tag AES-GCM falha → `InvalidTag` → rejeitada | `crypto/aead.py:63`, `client/peers.py:79-82` |
| Replay | `seq_no` ≤ último aceito → rejeitada | `client/peers.py:70` |
| Quadro forjado travar o contador | Contador só avança depois da tag válida | `client/peers.py:84-87` |
| Remetente falso | `sender_id` do servidor deve bater com o do quadro autenticado | `client/messaging.py`, `_receber_relay` |
| Framing inválido | Tamanho 0, > 64 KiB ou incompleto → erro e desconexão | `common/framing.py`, `ler_quadro` |
| Lista de chaves adulterada | HMAC + contador no canal de controle | `crypto/handshake.py`, `CanalAutenticado` |
| Vazamento em logs | Servidor loga só UUIDs e tamanho; chaves com `repr=False` | `server/relay.py`, `client/peers.py` |

---

## 8. Roteiro da apresentação (cerca de 15 minutos)

| # | Bloco | Quem | Tempo | Material |
| --- | --- | --- | --- | --- |
| 1 | Capa e objetivo | Ambos | 30 s | Slide 1 |
| 2 | Fluxo do protocolo | Ambos | 2 min | Slide 2 (seção 3 deste documento) |
| 3 | Algoritmos | Ambos | 1 min | Slide 3 |
| 4 | Servidor: identidade, handshake, sessões, relay, framing | Miqueias (Dev A) | 5–6 min | `server/*.py`, `crypto/handshake.py` |
| 5 | Cliente: ECDH, HKDF, AES-GCM, quadro, anti-replay | Rewelli (Dev B) | 5–6 min | `crypto/key_derivation.py`, `crypto/aead.py`, `client/peers.py` |
| 6 | Demonstração ao vivo | Ambos | 2–3 min | Slide 4 + terminais |
| 7 | Encerramento e perguntas | Ambos | 1 min | Seção 10 |

**Transição entre os dois:** o Dev A termina com "o servidor entrega a lista de chaves públicas e encaminha o payload sem abrir"; o Dev B começa com "a minha parte começa quando o cliente recebe essas chaves".

---

## 9. Demonstração

### Preparação (antes de começar)

Na raiz do projeto, confira que existem `.venv`, `secrets/server.key` e `certs/server.crt`. Se a identidade não existir, rode **uma vez** `.\.venv\Scripts\python.exe -m scripts.generate_server_keys`.

### Parte 1 — Sistema funcionando (três terminais)

```powershell
# Terminal 1 — Servidor
.\.venv\Scripts\python.exe -m src.server.main

# Terminal 2 — Cliente A
.\.venv\Scripts\python.exe -m src.client.main

# Terminal 3 — Cliente B
.\.venv\Scripts\python.exe -m src.client.main
```

| Passo | Ação | O que falar |
| --- | --- | --- |
| 1 | Iniciar servidor e os dois clientes | "Os dois clientes concluíram o handshake e entraram na lista." |
| 2 | `/id` e `/peers` nos clientes | "Cada um tem um UUID e vê a chave pública do outro, pela impressão digital." |
| 3 | No A: `/msg <8 primeiros caracteres do ID de B> mensagem confidencial` | "Bob recebeu o texto. No servidor aparece só origem, destino e tamanho." |
| 4 | Responder pelo B | "As duas direções usam chaves diferentes." |
| 5 | `/sair` no B | "A sessão foi removida e A recebeu o aviso de saída." |

### Parte 2 — Ataques sendo rejeitados (quarto terminal)

```powershell
.\.venv\Scripts\Activate.ps1
pytest -v -k bitflip_pela_rede          # bit alterado no caminho → rejeitado
pytest -v -k replay_pela_rede           # mesma mensagem duas vezes → rejeitada
pytest -v -k quadro_invalido            # framing inválido → desconexão
pytest -v -k "not persistencia"         # suíte completa: 148 testes
```

| Teste | O que acontece |
| --- | --- |
| `testar_bitflip_pela_rede_e_rejeitado` | Um relay malicioso inverte um bit em cada região do quadro; Bob rejeita, o contador não avança e a próxima mensagem é aceita. |
| `testar_replay_pela_rede_e_rejeitado` | O relay entrega o mesmo quadro duas vezes; a segunda é rejeitada como replay. |
| `testar_desconexao_por_quadro_invalido` | O cliente envia um prefixo de 65.537 bytes; o servidor fecha a conexão. |

O teste `testar_persistencia_identidade_permissoes_e_nao_sobrescrita` fica de fora porque verifica uma permissão de arquivo que só existe em Linux/macOS.

---

## 10. Perguntas prováveis

**O servidor consegue ler as mensagens?**
Não. Ele só conhece as chaves públicas; o segredo Z exige uma chave privada de cliente. O servidor vê metadados: UUIDs, tamanho e horário.

**E se o servidor for comprometido?**
O certificado protege contra um servidor *impostor*. Um servidor verdadeiro comprometido poderia trocar as chaves públicas da lista. Por isso o `/peers` mostra a impressão digital, que os usuários podem comparar por outro canal.

**O que dá o sigilo perfeito?**
As chaves X25519 são novas a cada conexão e descartadas ao sair. Se a chave RSA vazar no futuro, ela não permite recalcular conversas antigas.

**Para que serve o RSA, se ele não cifra nada?**
Só para assinar o handshake e provar que a resposta veio do servidor verdadeiro.

**Por que duas chaves AES?**
Uma por direção. Assim o mesmo par chave + nonce nunca é usado nos dois sentidos.

**Por que o salt é o mesmo para todos os clientes?**
A e B precisam do mesmo salt para derivar as mesmas chaves. Ele é gerado por execução do servidor. Na reconexão o salt se repete se o servidor não reiniciar, mas as chaves são novas porque o par X25519 muda. Teste: `testar_salt_comum_na_execucao_e_novo_apos_reinicio`.

**Por que AES-128 e não AES-256?**
O enunciado pede 128, e 128 bits seguem seguros.

**Onde fica a chave privada do servidor?**
Em `secrets/server.key`, só na máquina do servidor e fora do Git. Os clientes têm apenas o certificado público.

**Qual o limite de clientes e de texto?**
128 clientes simultâneos e 4096 bytes de texto por mensagem (em UTF-8, acentos ocupam mais de um byte).
