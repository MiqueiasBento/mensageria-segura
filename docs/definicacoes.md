# Plano de implementação — Trabalho Prático 3

Iniciar com aplicação pequena, organizada por responsabilidades, e adicionar os mecanismos criptográficos gradualmente. Como a linguagem, a divisão da dupla e o ambiente ainda não foram definidos, vou propor uma arquitetura inicial independente dessas decisões e indicar uma opção técnica recomendada.

O objetivo não é construir um aplicativo de mensagens completo, com interface gráfica, histórico e cadastro de usuários. É implementar e demonstrar corretamente o protocolo de mensageria segura exigido pelo professor.

## 1. Decisões técnicas iniciais

Minha recomendação provisória é utilizar Python, TCP com `asyncio` e a biblioteca `cryptography`, caso não exista uma exigência de linguagem por parte do professor.

| Decisão                | Proposta inicial                           | Justificativa                                                          |
| ---------------------- | ------------------------------------------ | ---------------------------------------------------------------------- |
| Linguagem              | Python                                     | Facilita implementar e inspecionar os mecanismos criptográficos.       |
| Rede                   | TCP com `asyncio`                          | Permite atender múltiplos clientes simultaneamente.                    |
| Criptografia           | Biblioteca `cryptography`                  | Disponibiliza primitivas para RSA-PSS, X25519, HKDF e AES-GCM.         |
| Interface              | Terminal (CLI)                             | Reduz o escopo e facilita demonstrar os testes.                        |
| Protocolo de mensagens | Quadros binários com comprimento prefixado | Segue a orientação de framing TCP do professor.                        |
| Testes                 | Testes automatizados e demonstração manual | Permite reproduzir falhas de segurança de forma controlada.            |
| Controle de versão     | Git com integração frequente               | Evita que os módulos desenvolvidos pela dupla se tornem incompatíveis. |

A proposta é uma recomendação de implementação, não uma exigência adicional do professor. As exigências de X25519, RSA-PSS, HKDF-SHA256, AES-128-GCM e framing de 4 bytes vêm do material da disciplina.&#x20;

Orientações Trabalho Prático 2.pdf



## 2. Estrutura inicial do projeto

Sugiro organizar o repositório por componentes técnicos, separando o servidor, o cliente, os mecanismos criptográficos, o protocolo e os testes.

```
mensageria-segura/
├── README.md
├── pyproject.toml
├── .gitignore
├── certs/
│   ├── server.crt
│   └── README.md
├── scripts/
│   └── generate_server_keys.py
├── src/
│   └── secure_messaging/
│       ├── common/
│       │   ├── protocol.py
│       │   ├── framing.py
│       │   └── constants.py
│       ├── crypto/
│       │   ├── identity.py
│       │   ├── handshake.py
│       │   ├── key_derivation.py
│       │   └── aead.py
│       ├── server/
│       │   ├── main.py
│       │   ├── connection.py
│       │   ├── sessions.py
│       │   └── relay.py
│       └── client/
│           ├── main.py
│           ├── connection.py
│           ├── peers.py
│           └── messaging.py
├── tests/
│   ├── test_framing.py
│   ├── test_handshake.py
│   ├── test_key_derivation.py
│   ├── test_aead.py
│   ├── test_replay.py
│   ├── test_tampering.py
│   └── test_integration.py
└── docs/
    ├── protocol.md
    ├── architecture.md
    └── test-plan.md
```

Esta é uma estrutura proposta para Python. Se vocês escolherem Java, por exemplo, os diretórios serão substituídos por pacotes equivalentes, mantendo as mesmas responsabilidades.

### Responsabilidade de cada módulo

| Módulo                     | Responsabilidade                                                                               |
| -------------------------- | ---------------------------------------------------------------------------------------------- |
| `common/protocol.py`       | Definir os tipos de mensagens e os campos do protocolo.                                        |
| `common/framing.py`        | Codificar e decodificar quadros TCP prefixados por comprimento.                                |
| `crypto/identity.py`       | Gerar e carregar as chaves RSA e o certificado do servidor.                                    |
| `crypto/handshake.py`      | Implementar assinatura, validação e troca de dados do handshake.                               |
| `crypto/key_derivation.py` | Calcular ECDH e derivar chaves com HKDF.                                                       |
| `crypto/aead.py`           | Cifrar e decifrar mensagens usando AES-GCM.                                                    |
| `server/sessions.py`       | Manter as conexões, identificadores, chaves públicas e contadores administrativos necessários. |
| `server/relay.py`          | Localizar o destinatário e encaminhar quadros sem decifrar o conteúdo E2E.                     |
| `client/peers.py`          | Manter o estado criptográfico de cada outro cliente.                                           |
| `client/messaging.py`      | Preparar, cifrar, transmitir, receber e validar mensagens.                                     |
| `tests/`                   | Verificar os requisitos funcionais e de segurança.                                             |

Não é necessário criar todos esses arquivos de imediato. A estrutura serve como destino; vocês podem criar os módulos à medida que forem necessários.

### Uma distinção importante

O servidor e o cliente precisam manter estados diferentes.

O servidor mantém conexões ativas, identificadores, chaves públicas dos clientes e contadores das mensagens administrativas. Já cada cliente mantém suas próprias chaves privadas e o estado criptográfico das conversas, incluindo chaves de envio e recebimento, contadores e valores-base dos nonces.

As chaves simétricas E2E não devem ser armazenadas no servidor. Essa separação é essencial para atender ao requisito de relay sem capacidade de decifrar mensagens.&#x20;

Orientações Trabalho Prático 2.pdf



## 3. Sequência de implementação

A ordem abaixo foi pensada para evitar que um problema de criptografia seja confundido com um problema de rede ou de estrutura de mensagens.

### 01 - Comunicação TCP e framing
Dias 1–2

Criar servidor e clientes capazes de se conectar simultaneamente. Implementar o prefixo de 4 bytes, a leitura de quadros completos e a validação dos comprimentos.

Critério de conclusão:

Dois clientes conectam e trocam mensagens de teste pelo servidor, ainda sem criptografia.

### 02 - Registro e gerenciamento de sessões
Dia 3

Implementar `client_id`, registro de chaves públicas, distribuição das chaves entre os clientes e remoção das sessões quando houver desconexão.

Critério de conclusão:

O servidor reconhece os clientes conectados e distribui as chaves públicas corretas.

### 03 - Handshake autenticado
Dias 4–5

Implementar a geração das chaves RSA do servidor, o certificado confiável, a assinatura RSA-PSS e a validação realizada pelos clientes.

Critério de conclusão:

O handshake válido é aceito; um certificado não confiável ou uma assinatura inválida é rejeitado.

### 04 - Derivação de chaves e AES-GCM
Dias 6–7

Implementar X25519, o segredo ECDH, HKDF-SHA256, as chaves direcionais e a cifragem e decifragem AES-128-GCM.

Critério de conclusão:

Dois clientes derivam chaves compatíveis e trocam mensagens E2E através do relay.

### 05 - Contadores, nonces e proteção contra ataques
Dias 8–9

Implementar a sequência monotônica por direção, AAD, rejeição de replays, tratamento de falhas da tag GCM e erros de framing.

Critério de conclusão:

Os testes de adulteração, replay e framing inválido são reproduzíveis e passam.

### 06 - Integração, documentação e demonstração
Dia 10 em diante

Revisar a política de logs, testar reconexões, documentar o protocolo e preparar a apresentação dos dois integrantes.

Critério de conclusão:

O sistema pode ser iniciado do zero e todos os cenários obrigatórios podem ser demonstrados sem correções manuais no meio da execução.

As durações são estimativas para planejamento, não garantias de execução. O ideal é reservar os últimos dias exclusivamente para integração e correção, evitando novas funcionalidades nessa fase.

## 4. Cuidados técnicos que devem ser resolvidos antes da implementação criptográfica

Há uma ambiguidade relevante no material do professor: ele menciona a assinatura de uma chave efêmera ECDHE na descrição geral, mas a fórmula detalhada da assinatura apresenta `pk_server || pk_client || client_id || salt`, sem deixar inteiramente clara a distinção entre a chave pública RSA do servidor e uma eventual chave efêmera X25519 do servidor.

Como o protocolo também utiliza chaves X25519 efêmeras dos próprios clientes para a comunicação E2E, não devemos presumir que esses elementos sejam intercambiáveis.

Antes de implementar o handshake, vale confirmar com o professor exatamente qual chave pública deve ser assinada e qual deve ser incluída na fórmula do hash. Isso evita implementar uma interpretação que funcione tecnicamente, mas não corresponda ao protocolo esperado na avaliação.

Outros cuidados:

- Não reutilizar um nonce com a mesma chave AES-GCM.
- Não avançar o contador de recebimento antes de a autenticação da mensagem ser validada.
- Não confiar em uma chave pública apenas porque ela foi recebida do servidor; o mecanismo de autenticação especificado precisa proteger a etapa correspondente.
- Não registrar segredos, chaves privadas ou conteúdo das mensagens em logs.
- Não considerar a implementação concluída apenas porque a mensagem pode ser decifrada: os testes negativos também precisam funcionar.

## 5. Como organizar a dupla e o repositório

Eu evitaria deixar cada integrante desenvolver um subsistema inteiro por vários dias sem integração. Isso aumenta o risco de incompatibilidade no formato das mensagens e nos parâmetros criptográficos.

Uma divisão inicial possível é:

| Integrante A                                             | Integrante B                                 |
| -------------------------------------------------------- | -------------------------------------------- |
| Servidor TCP, sessões e relay                            | Cliente TCP, framing e interface de terminal |
| Registro e distribuição das chaves públicas              | ECDH, HKDF e AES-GCM                         |
| Handshake RSA-PSS em conjunto com o módulo de identidade | Contadores, nonces e testes de replay        |

Essa divisão pode ser ajustada de acordo com o conhecimento de cada integrante. O handshake deve ser integrado e revisado pelos dois, porque conecta a autenticação à derivação das chaves.

No Git, criem um repositório compartilhado com uma branch principal protegida e branches curtas por funcionalidade. Cada módulo deve ser integrado assim que seus testes básicos passarem. O protocolo e o formato dos quadros devem ser acordados antes que cliente e servidor sejam implementados separadamente.

## 6. Checklist de conclusão

## Acompanhamento

0/15 concluídos

Rede e protocolo
- [ ] Servidor aceita múltiplas conexões TCP
- [ ] Framing por comprimento de 4 bytes funciona
- [ ] Registro e distribuição de chaves públicas funcionam

Criptografia
- [ ] Handshake e validação da assinatura funcionam
- [ ] ECDH e HKDF geram chaves compatíveis
- [ ] Mensagens E2E usam AES-128-GCM corretamente

Segurança
- [ ] Adulteração é rejeitada
- [ ] Replay é rejeitado
- [ ] Framing inválido é tratado com segurança
- [ ] Reconexão estabelece novas chaves
- [ ] Logs não expõem segredos

Entrega
- [ ] Testes automatizados executam de forma reproduzível
- [ ] README explica como executar o sistema
- [ ] Documentação descreve o protocolo
- [ ] Ambos os integrantes conseguem explicar o código

A checklist serve para acompanhar a evolução, mas não substitui a execução dos testes: cada item deve ser marcado apenas quando houver evidência de que o requisito foi atendido.

Até definir todos os pontos, sugestão é seguir esta ordem:
1. Fechar as decisões de serialização e enquadramento.
2. Implementar a comunicação TCP entre servidor e dois clientes.
3. Validar registro, lista de clientes e encaminhamento de mensagens simples.
4. Só então começar a camada criptográfica.