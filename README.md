# Mensageria Segura | Segurança de Software

Trabalho prático de Segurança de Software — Prof. Michel Sales.

Servidor TCP com identidade RSA-PSS e clientes de terminal com X25519, HKDF-SHA256, AES-128-GCM e proteção contra replay. O servidor distribui chaves públicas por um canal autenticado e encaminha o conteúdo cifrado sem possuir as chaves E2E dos pares.

## Preparar e executar

Requisito: Python 3.11 ou superior. A validação desta entrega usou Python 3.12.3.

Na raiz do repositório, em Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.generate_server_keys
```

O último comando é executado **uma vez**: cria `secrets/server.key` e `certs/server.crt`. Ele recusa sobrescrever arquivos existentes. A chave privada fica somente no servidor, com permissão `0600`; esses dois arquivos locais são ignorados pelo Git. No mesmo computador, os clientes já usam o certificado gerado. Em computadores diferentes, copie **somente o certificado** do servidor para os clientes por um meio confiável antes de conectar. Consulte [certs/README.md](certs/README.md).

Abra três terminais na raiz do projeto:

```sh
.venv/bin/python -m src.server.main    # terminal 1
.venv/bin/python -m src.client.main    # terminal 2: Alice
.venv/bin/python -m src.client.main    # terminal 3: Bob
```

No Windows/PowerShell, crie o ambiente com `py -m venv .venv` e substitua `.venv/bin/python` por `.venv\Scripts\python.exe` nos comandos. A permissão POSIX `0600` se aplica a Linux/macOS; proteja a pasta `secrets` com as permissões do Windows.

O endereço padrão é `127.0.0.1:8000`. Ambos os programas aceitam `--host` e `--port`. O cliente aceita `--certificado CAMINHO`; o servidor aceita `--chave CAMINHO` e `--certificado CAMINHO`. Se o certificado ou a chave estiverem ausentes, inválidos ou incompatíveis, corrija o provisionamento antes de iniciar. O cliente não aceita automaticamente um certificado recebido na rede.

## Usar o chat

| Comando | Ação |
| --- | --- |
| `/peers` | Lista participantes, UUID completo e impressão digital da chave pública. |
| `/msg <id> <texto>` | Envia texto ao UUID completo ou a um prefixo único, por exemplo, os oito primeiros caracteres. |
| `/id` | Mostra o próprio UUID. |
| `/ajuda` | Mostra os comandos. |
| `/sair` | Fecha a conexão e remove a sessão. |

Em Alice, use `/peers` e copie o ID de Bob. Envie `/msg <id-de-Bob> olá, Bob`. Responda pelo terminal de Bob usando o ID de Alice. Saia com `/sair`. Pare o servidor com `Ctrl+C`.

## Verificar a entrega

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -v tests/test_handshake.py tests/test_server_handshake.py
.venv/bin/python -m pytest -v tests/test_tampering.py tests/test_replay.py tests/test_integration.py
```

Resultado em 03/11/2026: **149 testes aprovados**. Os testes geram identidade temporária própria e não exigem os arquivos locais de produção. O ambiente deve permitir sockets TCP locais. Também foi validada a demonstração com três processos de terminal.

## Documentação e decisões

- [Relatório de progresso do Dev A](docs/relatorio-progresso-dev-a.md): implementação, decisões assumidas e evidências.
- [Protocolo](docs/protocol.md): bytes assinados, mensagens, chaves e contadores.
- [Arquitetura](docs/architecture.md): componentes e responsabilidades.
- [Plano de testes](docs/test-plan.md): critérios de aceitação e roteiro de demonstração.
- [Relatório histórico do Dev B](docs/relatorio-dev-b.md): entrega anterior à integração do handshake.
- [Diagramas da apresentação](docs/diagramas-apresentacao.md): arquitetura, handshake, relay, quadros e chaves em um só arquivo.

O servidor é a autoridade confiável para o diretório de chaves. O certificado pinado protege contra servidores impostores. Um servidor comprometido que controla a chave RSA pode falsificar o diretório; resistir a esse cenário exigiria autenticação independente das chaves dos usuários. UUIDs identificam sessões, não comprovam a identidade de pessoas. O canal administrativo autentica metadados, mas não os cifra. Somente as mensagens entre clientes têm confidencialidade E2E.
