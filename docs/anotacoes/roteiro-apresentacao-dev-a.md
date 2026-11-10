# Roteiro curto de apresentação — Dev A

**Objetivo:** apresentar sua parte em cerca de 5 a 7 minutos, com uma demonstração simples. Use as falas abaixo como base; elas já fazem a transição entre os arquivos. Você precisa abrir **quatro arquivos principais**: `src/server/main.py`, `src/server/connection.py`, `src/server/sessions.py` e `src/server/relay.py`. Deixe `src/crypto/handshake.py` e `src/common/framing.py` preparados em abas para mostrar se houver tempo ou pergunta.

**Ordem para lembrar:** iniciar servidor → autenticar cliente → registrar sessão → encaminhar mensagem → remover sessão. O Dev B explica com mais detalhe como os clientes cifram e decifram.

## 1. Abertura e arquitetura — cerca de 40 segundos

**Mostre:** o diagrama em [architecture.md](../architecture.md). Depois abra [server/main.py](../../src/server/main.py), função `iniciar_servidor` (linhas 16–22).

**Fale:**

> “Nosso projeto é um chat de terminal para dois ou mais clientes. Existe um servidor TCP no meio da comunicação. Ele recebe conexões, mantém uma lista de clientes online e entrega cada mensagem ao destinatário.
>
> A proteção do texto acontece nos clientes: Alice cifra antes de enviar; Bob decifra ao receber. O servidor participa do transporte, mas não tem a chave usada para ler essa conversa. Minha parte foi implementar o servidor, as sessões, o encaminhamento e a autenticação inicial da conexão.
>
> [Aponte `asyncio.start_server`.] Esta chamada abre a porta TCP. Para cada cliente conectado, ela executa `atender_cliente`. Vou mostrar primeiro como o servidor se identifica e depois como trata essa conexão.”

**Guarde esta frase:** “O servidor vê metadados, como UUIDs e tamanho do quadro; a confidencialidade E2E protege o texto da conversa.” Evite dizer que o servidor não vê nada.

## 2. Identidade e entrada do cliente — cerca de 1 minuto e 30 segundos

**Mostre:** [server/main.py](../../src/server/main.py), linhas 16–22 e 31–43; depois [server/connection.py](../../src/server/connection.py), linhas 38–68. Se perguntarem sobre assinatura, abra [crypto/handshake.py](../../src/crypto/handshake.py), funções `criar_handshake` e `validar_handshake` (linhas 104–144).

**Fale:**

> “Antes de alguém se conectar ao servidor, ele precisa ter uma identidade criptográfica. É uma forma de comprovar que a resposta inicial veio do servidor esperado. Essa identidade tem uma chave RSA privada, que fica no servidor, e um certificado com a chave pública, que é entregue previamente aos clientes.
>
> [Em `server/main.py`, aponte `carregar_identidade`.] O servidor carrega essa identidade antes de abrir a porta. Também gera um salt aleatório para esta execução. O salt ajuda na derivação de chaves; ele não é secreto.
>
> [Em `server/connection.py`, aponte `REGISTER`.] Quando Alice entra, ela envia seu UUID e uma chave pública temporária X25519. O servidor responde com `HANDSHAKE`: envia sua chave pública temporária, o certificado, o salt e uma assinatura RSA-PSS desses dados vinculados à chave e ao UUID de Alice.
>
> O cliente só aceita a resposta se o certificado corresponder à cópia confiável que já tinha e se a assinatura for válida. Depois, cliente e servidor calculam chaves para autenticar as mensagens de controle. Alice envia uma confirmação chamada `READY`. [Aponte o teste de `READY` e, logo abaixo, `registrar_cliente`.] O servidor só registra Alice após validar essa confirmação. Assim, uma conexão incompleta não aparece como cliente online.”

**Se perguntarem “o que RSA faz?”** Responda: “RSA-PSS assina o handshake e autentica o servidor. Não cifra as mensagens do chat.” O certificado é autoassinado; a confiança vem da cópia provisionada antes da conexão. A chave privada e o certificado são criados por [generate_server_keys.py](../../scripts/generate_server_keys.py).

## 3. Sessões, lista e saída — cerca de 1 minuto

**Mostre:** [server/sessions.py](../../src/server/sessions.py), classes `Sessao` e `RegistroSessoes` (linhas 9–45); depois [server/connection.py](../../src/server/connection.py), linhas 56–68 e 82–94.

**Fale:**

> “Depois do `READY`, o servidor cria uma sessão. Ela guarda o UUID, a chave pública do cliente, a conexão TCP e o canal administrativo autenticado. O servidor não guarda nessa sessão a chave AES que Alice e Bob usam para a conversa.
>
> [Aponte o dicionário de sessões e `registrar_cliente`.] O diretório permite localizar quem está online. Ele rejeita um UUID que já esteja ativo e limita o número de clientes registrados a 128.
>
> [Volte a `server/connection.py`.] Ao entrar, Alice recebe `CLIENT_LIST` com os clientes existentes; os demais recebem `CLIENT_JOINED`. Ao sair, a sessão é removida e os outros recebem `CLIENT_LEFT`. Uma trava organiza essas mudanças quando várias conexões acontecem quase ao mesmo tempo.”

**Se perguntarem “UUID identifica a pessoa?”** Responda: “Não. É um identificador da sessão criado pelo cliente; não há cadastro de identidade civil.”

## 4. Relay e mensagens protegidas — cerca de 1 minuto

**Mostre:** [server/relay.py](../../src/server/relay.py), função `encaminhar` (linhas 6–24). Aponte especialmente `obter_cliente` e `"payload": mensagem["payload"]`.

**Fale:**

> “Quando Alice envia texto, o cliente dela cifra antes de chamar o servidor. O servidor recebe um pedido `RELAY` com o destino e um `payload` que contém o quadro E2E cifrado.
>
> [Aponte `encaminhar`.] Aqui o servidor valida o destino e o tamanho do `payload`, procura a sessão de Bob e repassa o mesmo campo `payload`. O UUID do remetente é obtido da sessão autenticada de Alice. O servidor não chama uma função de decifragem e não tem as chaves AES da conversa.
>
> Se Bob não estiver conectado, Alice recebe `UNKNOWN_CLIENT`, mas sua conexão continua funcionando. O log do servidor mostra origem, destino e quantidade de bytes, sem o texto da mensagem.”

**Precisão importante:** o **quadro E2E dentro do `payload`** é preservado. O JSON externo muda porque o servidor acrescenta `sender_id` e autentica um novo envelope para Bob.

## 5. Framing e proteção de entrada — cerca de 30 segundos, se houver tempo

**Mostre:** [common/framing.py](../../src/common/framing.py), função `ler_quadro` (linhas 12–25).

**Fale:**

> “TCP entrega um fluxo de bytes, então um envio pode chegar em pedaços. Por isso cada quadro começa com quatro bytes que informam o tamanho do corpo. O leitor espera o corpo completo e rejeita tamanho zero, quadro incompleto ou tamanho acima de 64 KiB. O servidor trata o erro e fecha a conexão problemática.”

**Se perguntarem sobre JSON:** [common/protocol.py](../../src/common/protocol.py) rejeita campos repetidos, UUID inválido, chave pública com tamanho errado e `payload` acima de 4.164 bytes.

## 6. Demonstração em três terminais — cerca de 2 minutos

Prepare antes da apresentação, na raiz do projeto. Execute o gerador **só se a identidade ainda não existir**:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m scripts.generate_server_keys
```

Abra três terminais, todos na raiz:

```sh
# Terminal 1
.venv/bin/python -m src.server.main
# Terminal 2
.venv/bin/python -m src.client.main
# Terminal 3
.venv/bin/python -m src.client.main
```

**Enquanto executa, fale apenas isto:**

1. **Inicie servidor e dois clientes:** “O servidor abriu a porta; Alice e Bob concluíram o handshake e entraram no diretório.”
2. **Use `/id` e `/peers` nos clientes:** “Cada um tem um UUID e consegue ver a chave pública do outro.”
3. **Em Alice, digite `/msg <id-de-Bob> mensagem confidencial`. Em Bob, responda:** “O texto aparece nos clientes. No servidor, vemos apenas origem, destino e tamanho do quadro.”
4. **Digite `/sair` em Bob:** “A sessão de Bob foi removida e Alice recebeu o aviso de saída.”

O comando `/msg` aceita o UUID completo ou um prefixo único. Encerre o servidor com `Ctrl+C`. Se já houver uma identidade local, **não** execute de novo `generate_server_keys`, pois ele recusa sobrescrevê-la.

## 7. Testes para mostrar — cerca de 40 segundos

```sh
.venv/bin/python -m pytest -q
```

**Fale:**

> “A demonstração mostra o uso normal. Os testes verificam também casos de falha: certificado ou assinatura inválidos impedem o handshake; mensagem E2E adulterada é rejeitada; repetir um quadro E2E já aceito gera rejeição por replay; e quadros TCP inválidos são recusados. O resultado exibido agora corresponde aos casos automatizados, não a uma auditoria formal.”

Se o professor pedir o código dos testes, abra:

| Pergunta | Teste |
| --- | --- |
| Certificado ou assinatura errada | [test_server_handshake.py](../../tests/test_server_handshake.py), `testar_certificado_errado_impede_registro` e `testar_handshake_adulterado_na_rede_fecha_cliente` |
| Adulteração e replay E2E | [test_integration.py](../../tests/test_integration.py), `testar_bitflip_pela_rede_e_rejeitado` e `testar_replay_pela_rede_e_rejeitado` |
| Quadros TCP inválidos | [test_framing.py](../../tests/test_framing.py), testes de tamanho e incompletude |

**Fale com precisão se perguntarem:** ainda falta um teste único que compare byte a byte um quadro E2E real na entrada e na saída do relay. Também não há teste de rede que prove nova conexão após **cada** tipo de quadro inválido. O código do relay preserva o `payload`, e os testes atuais verificam as partes desse fluxo separadamente.

## 8. Encerramento — cerca de 20 segundos

**Fale:**

> “Minha parte garante que o servidor inicia com uma identidade, só registra o cliente depois do handshake, mantém a lista de sessões e encaminha o conteúdo cifrado ao destinatário. A parte do Dev B detalha como os clientes criam as chaves e protegem cada mensagem com AES-GCM. Assim, o servidor organiza e transporta a conversa, e os clientes protegem o texto.”

## Cola de última hora

- **RSA-PSS:** assinatura do servidor no handshake.
- **X25519:** acordo de segredo; há um acordo cliente-servidor para o controle e outro entre clientes para E2E.
- **HMAC:** autentica lista, eventos e comandos administrativos; não os cifra.
- **AES-GCM:** cifra e autentica o texto entre clientes; Dev B explica os detalhes.
- **`READY`:** confirmação autenticada exigida antes do registro.
- **Sessão:** UUID + chave pública + conexão + canal administrativo.
- **Relay:** escolhe o destino e repassa o `payload` cifrado.
- **Limite de confiança:** o servidor controla o diretório de chaves públicas. Um servidor comprometido poderia substituir chaves; o projeto não autentica a identidade civil dos usuários.
