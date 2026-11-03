# Mensageria Segura | Segurança de Software

Trabalho prático 3 de Segurança de Software — Prof. Michel Sales.

Servidor TCP de registro e encaminhamento (*relay*) e clientes de terminal que trocam
mensagens cifradas ponta a ponta (X25519 + HKDF-SHA256 + AES-128-GCM, com `seq_no`
anti-replay). O servidor só vê quadros cifrados.

## Preparar o ambiente

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Os comandos abaixo supõem o ambiente virtual ativado.

## Executar (demo com 3 terminais)

```sh
python -m src.server.main      # terminal 1: servidor em 127.0.0.1:8000
python -m src.client.main      # terminal 2: Alice
python -m src.client.main      # terminal 3: Bob
```

`--host` e `--port` mudam o endereço do servidor no cliente. Comandos do chat:

| Comando | Ação |
| --- | --- |
| `/peers` | lista os peers (id curto, id completo e fingerprint da chave pública) |
| `/msg <id> <texto>` | envia texto cifrado E2E; aceita um prefixo único do id (ex.: os 8 primeiros caracteres) |
| `/id` | mostra o próprio `client_id` |
| `/ajuda` | mostra os comandos |
| `/sair` | desconecta |

## Testes

```sh
python -m pytest -q
python -m pytest -v tests/test_tampering.py tests/test_replay.py tests/test_integration.py   # demo de ataques
```

| Arquivo | O que cobre |
| --- | --- |
| `test_framing.py`, `test_initial_server.py` | framing de 4 bytes, registro, relay e desconexão no servidor |
| `test_key_derivation.py` | X25519/ECDH, HKDF Extract + Expand (vetor RFC 5869), chaves A2B/B2A |
| `test_aead.py` | AES-128-GCM, nonce, AAD e montagem do quadro E2E |
| `test_replay.py`, `test_tampering.py` | contadores, replay e bitflip em cada região do quadro |
| `test_client_connection.py` | camada de rede do cliente contra o servidor real |
| `test_integration.py` | servidor + clientes reais: E2E, só o destinatário decifra, replay e bitflip injetados no relay, reconexão com chaves novas, quadro inválido do servidor e logs sem segredos |
| `test_handshake.py` | **pendente** — handshake RSA-PSS (Integrante A) |

## Documentação

- [docs/protocol.md](docs/protocol.md) — protocolo e formato dos quadros.
- [docs/anotacoes/etapa-inicial.md](docs/anotacoes/etapa-inicial.md) — servidor, framing e contrato JSON.
- [docs/anotacoes/etapa-cliente-cripto.md](docs/anotacoes/etapa-cliente-cripto.md) — cliente, criptografia E2E e pontos de integração com o handshake.

## Estado atual

O canal E2E está completo, mas **o handshake autenticado ainda não foi integrado**: o
cliente usa `SALT_PROVISORIO` (16 bytes zero) e confia nas chaves públicas distribuídas
pelo servidor. Até o handshake RSA-PSS com certificado pinado ser implementado, um
servidor malicioso poderia trocar as chaves públicas (MITM).
