## 1. Primeiro, prepare o ambiente

Considerando a arquitetura que criamos, recomendo:

- Python 3.
- Ambiente virtual (`venv`).
- `asyncio` para comunicação TCP.
- `pytest` para testes.
- Git para versionamento.

Na raiz do projeto, execute:

```
python3 -m venv .venv
source .venv/bin/activate

pip install pytest pytest-asyncio cryptography
```

Depois, registre as dependências:

```
pip freeze > requirements.txt
```

Não precisamos instalar FastAPI, Flask ou qualquer framework web.

## 2. Sua primeira responsabilidade: implementar o servidor TCP

Comece pelo módulo:

```
src/secure_messaging/server/
├── main.py
├── connection.py
├── sessions.py
└── relay.py
```

A responsabilidade de cada arquivo será:

| Arquivo         | Responsabilidade                                    |
| --------------- | --------------------------------------------------- |
| `main.py`       | Inicializar o servidor e aguardar conexões.         |
| `connection.py` | Gerenciar a comunicação TCP com cada cliente.       |
| `sessions.py`   | Registrar, consultar e remover clientes conectados. |
| `relay.py`      | Encaminhar mensagens de um cliente para outro.      |

Não tente implementar tudo de uma vez. Vamos seguir uma sequência incremental.

## 3. Ordem de implementação

Eu dividiria seu trabalho em quatro pequenas entregas.

### Etapa 1 — Servidor TCP funcionando

Implemente inicialmente apenas a capacidade de aceitar conexões e identificar quando um cliente conecta ou desconecta.

Em `server/main.py`, você pode começar com:

```
import asyncioHOST = "127.0.0.1"PORT = 8000async def handle_client(reader, writer):    address = writer.get_extra_info("peername")    print(f"Cliente conectado: {address}")    try:        while True:            data = await reader.read(1024)            if not data:                break            print(f"Dados recebidos: {data}")    except Exception as error:        print(f"Erro na conexão: {error}")    finally:        print(f"Cliente desconectado: {address}")        writer.close()        await writer.wait_closed()async def main():    server = await asyncio.start_server(        handle_client,        HOST,        PORT    )    print(f"Servidor iniciado em {HOST}:{PORT}")
```

Esse código é apenas um ponto de partida para testar conexões TCP. Ainda não implementa framing, registro ou segurança.

Critério de conclusão: conseguir iniciar o servidor e conectar dois clientes simultaneamente, mantendo as duas conexões abertas.

### Etapa 2 — Gerenciamento de sessões

Depois, implemente `sessions.py`.

O servidor precisará manter uma estrutura que relacione o identificador de cada cliente à sua conexão.

Uma representação inicial seria:

```
sessions = {    client_id: {        "writer": writer,        "public_key": public_key    }}
```

As operações principais serão:

- `register_client()`: registrar um cliente.
- `get_client()`: localizar uma sessão.
- `remove_client()`: remover uma sessão.
- `get_all_clients()`: consultar os clientes conectados.

Não precisa implementar todas agora. Comece pelo registro e remoção.

Critério de conclusão: o servidor consegue identificar quais clientes estão conectados e remover corretamente uma sessão quando a conexão é encerrada.

### Etapa 3 — Registro e distribuição de chaves públicas

Aqui começamos a implementar as mensagens do protocolo.

O fluxo esperado será:

1. Cliente A conecta ao servidor.
2. Cliente A envia `REGISTER`, contendo seu identificador e sua chave pública.
3. Servidor registra A.
4. Cliente B conecta e também envia `REGISTER`.
5. Servidor registra B.
6. Servidor informa A sobre a entrada de B.
7. Servidor envia a B a lista de clientes ativos, incluindo A.

Nesse momento, ainda não precisamos calcular ECDH ou derivar chaves. O objetivo é apenas distribuir as chaves públicas.

Critério de conclusão: dois clientes conseguem se registrar e conhecer as chaves públicas um do outro por meio do servidor.

### Etapa 4 — Encaminhamento de mensagens

Por último, implemente `relay.py`.

O fluxo será:

1. Cliente A envia um quadro destinado a B.
2. Servidor identifica o destinatário.
3. Servidor encaminha os bytes recebidos para B.
4. B recebe o quadro.

Inicialmente, vocês podem testar com dados fictícios. Depois, substituem esses dados por quadros protegidos com AES-GCM.

Isso corresponde à arquitetura E2E do trabalho: o servidor encaminha as mensagens, mas não deve descriptografá-las.&#x20;

Orientações Trabalho Prático 2.pdf



## 4. O que você precisa combinar com o desenvolvedor B

Antes de avançar para as etapas 3 e 4, alinhe três coisas:

| Assunto      | O que combinar                                                           |
| ------------ | ------------------------------------------------------------------------ |
| Framing      | Qual função será utilizada para ler e escrever quadros TCP?              |
| Serialização | Vamos utilizar JSON UTF-8 nas mensagens de controle?                     |
| Interface    | Como o cliente enviará uma mensagem e receberá uma resposta do servidor? |

Uma sugestão de interface compartilhada:

```
async def read_frame(reader):    ...async def write_frame(writer, data):    ...
```

Essas funções devem ficar em `common/framing.py`, pois serão utilizadas tanto pelo cliente quanto pelo servidor. Combinem quem implementará esse módulo para evitar trabalho duplicado.

## 5. O que não deve ser implementado ainda

Não comece agora por:

- RSA-PSS e validação de assinatura;
- ECDH e HKDF;
- AES-GCM;
- Nonces e contadores;
- Proteção contra replay.

Essas partes dependem de decisões e integrações que ainda estão pendentes. Você pode estudá-las em paralelo, mas não precisa bloquear o desenvolvimento do servidor por causa delas.

## Seu primeiro objetivo prático

Primeira entrega

Quero que você chegue a este resultado:

Servidor iniciado

Servidor escutando na porta 8000.

Cliente A consegue conectar.

Cliente B consegue conectar simultaneamente.

Servidor identifica as duas conexões.

Servidor identifica quando um cliente desconecta.

Esses são os critérios esperados, não funcionalidades já implementadas.

Minha orientação para trabalharmos: avance nessa primeira etapa e me envie o código que você produzir. Vou revisar a implementação, explicar eventuais problemas e orientar a próxima evolução. Não quero que você apenas copie soluções: quero que entenda por que estamos construindo cada componente e como ele participa do protocolo.
## Registro da implementação — 27/10/2026

As quatro etapas iniciais foram implementadas em `src/server/` e `src/common/`.
As decisões abaixo fecham os pontos de integração com o desenvolvedor B para esta fase:

| Assunto | Decisão implementada | Motivo |
| --- | --- | --- |
| Framing | `ler_quadro(leitor)` e `escrever_quadro(escritor, dados)` em `src/common/framing.py`; prefixo unsigned de 4 bytes, big-endian, que indica o tamanho do corpo. Limite de 64 KiB; quadro vazio, excessivo ou truncado encerra a conexão. | API compartilhada para cliente e servidor; leitura exata evita interpretar fragmentos TCP como mensagens completas. |
| Serialização | Mensagens de controle em JSON UTF-8 em `src/common/protocol.py`; chave pública X25519 e payload de relay em Base64; UUIDv4 em texto canônico. | Facilita a inspeção nesta fase sem alterar o formato binário E2E previsto para a etapa criptográfica. |
| Interface cliente-servidor | Cliente abre TCP, envia `REGISTER` primeiro, recebe `CLIENT_LIST`; os demais recebem `CLIENT_JOINED`. Cliente envia `RELAY` com `recipient_id` e `payload`; destino recebe `RELAY` com `sender_id`, `recipient_id` e o mesmo `payload`. Ao sair, os demais recebem `CLIENT_LEFT`. | Define o contrato necessário para implementar o cliente em paralelo. |

Exemplo de registro: `{"type":"REGISTER","client_id":"<uuidv4>","client_public_key":"<base64 de 32 bytes>"}`.
O servidor associa o remetente à conexão registrada e não aceita `sender_id` fornecido pelo cliente no relay. IDs duplicados, chaves fora do tamanho esperado e mensagens fora da ordem são rejeitados. As sessões ficam apenas em memória e são removidas na desconexão.

Nesta fase, o `payload` é opaco para o servidor, mas **ainda não é criptografado nem autenticado**. A distribuição das chaves públicas também ainda não é autenticada. Portanto, esta entrega demonstra transporte e roteamento, não mensageria segura completa. O cliente futuro deverá gerar uma nova chave efêmera a cada conexão; o servidor já aceita a chave pública que ele fornecer no registro.

### Critérios de aceitação desta etapa

| Critério | Estado | Evidência |
| --- | --- | --- |
| Servidor escuta em `127.0.0.1:8000` | Atendido | `python -m src.server.main`; constantes em `main.py`. |
| Dois clientes conectam simultaneamente | Atendido | Teste `testar_registro_encaminhamento_e_desconexao`. |
| Servidor identifica conexão e desconexão | Atendido | Logs de endereço e teste de remoção de sessão. |
| Registro e distribuição de chaves públicas | Atendido | Teste de `CLIENT_LIST` e `CLIENT_JOINED` com chaves distintas. |
| Encaminhamento de dados fictícios sem decifrar | Atendido | Teste do `payload` preservado entre origem e destino. |
| Framing inválido é tratado | Atendido nesta fase | Teste de comprimento excessivo, quadro vazio e leitura exata. |

Execução de verificação: `.venv/bin/python -m pytest -q tests/test_initial_server.py` → **3 passed**. Os testes de integração usam sockets TCP locais e precisam de um ambiente que permita bind em `127.0.0.1`.

### Próxima integração

O desenvolvedor B pode usar `src/common/framing.py` e o contrato acima para criar o cliente. Antes de tratar o canal como seguro, ainda faltam handshake autenticado, derivação ECDH/HKDF, AES-GCM, contadores, proteção contra replay e testes negativos correspondentes. O `RELAY` JSON desta fase é provisório; a integração E2E deve definir a transição para o quadro binário descrito em `docs/protocol.md`.

### Convenção de nomes

Variáveis, funções, métodos e classes da implementação estão em português. Os nomes dos módulos e as chaves/valores JSON (`type`, `client_id`, `REGISTER` etc.) permanecem como definidos no contrato de rede. Bibliotecas externas mantêm suas APIs originais.
