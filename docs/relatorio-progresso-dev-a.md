# Relatório de progresso — Dev A

Data: 03/11/2026. Responsável: Miquéias (Dev A). Este relatório descreve a integração com a entrega do Dev B.

## Decisões assumidas sem resposta do professor

1. `pk_server` é a chave pública X25519 efêmera do servidor, renovada por conexão. A chave RSA de identidade assina `SHA256(pk_server || pk_client || client_id || salt_srv)`. Os tamanhos são 32, 32, 16 e 16 bytes. RSA-PSS usa SHA256, MGF1-SHA256 e salt de assinatura de 32 bytes. `Prehashed` evita calcular o hash duas vezes.
2. A identidade usa RSA de 3072 bits e certificado X.509 autoassinado, válido por 365 dias. O cliente exige o certificado provisionado previamente e verifica sua vigência. Não existe aceitação automática de certificado recebido na rede.
3. `salt_srv` tem 16 bytes aleatórios por execução do servidor, comuns aos clientes dessa execução. Uma reconexão renova as chaves efêmeras. O salt não precisa mudar em cada reconexão porque o segredo ECDH muda. Isso substitui o salt zero e resolve a necessidade de igualdade entre os dois lados de cada par.
4. O acordo X25519 cliente-servidor deriva duas chaves HMAC administrativas. Elas são distintas das chaves E2E entre clientes. Um envelope autenticado vincula a mensagem à conexão e ao contador em cada direção. Essa extensão protege listas de chaves e eventos após o handshake.
5. O servidor é a autoridade confiável do diretório de chaves públicas. A identidade RSA protege contra um servidor impostor na rede. Um servidor comprometido que possui a chave RSA ainda pode falsificar o diretório. O trabalho não implementa identidade civil dos usuários nem autenticação externa das chaves dos peers.

As decisões são escolhas desta implementação. Não são confirmações do professor. O PDF original não está disponível neste checkout; a implementação usa os requisitos transcritos em `docs/protocol.md` e `docs/definicacoes.md`.

## Parte 1 — Identidade e mecanismos do handshake

Implementados `identity.py`, `handshake.py` e o gerador executável por módulo. A gravação da chave privada usa permissão `0600` e recusa sobrescrever arquivos existentes. O certificado deve corresponder à chave privada. Certificado e chave locais ficam fora do Git; o certificado vazio anterior foi removido.

O cliente verifica o certificado pinado, a assinatura e o vínculo com sua própria chave pública e UUID. O canal administrativo usa HMAC-SHA256, chaves direcionais e sequência estrita sobre JSON canônico. MAC ou sequência inválida não avançam o contador.

Validação desta parte: 18 testes aprovados de identidade, handshake, adulteração, pinning, sequência e persistência. Referências: [RSA e Prehashed](https://cryptography.io/en/41.0.7/hazmat/primitives/asymmetric/rsa/) e [certificados X.509](https://cryptography.io/en/latest/x509/reference/).

## Parte 2 — Integração entre servidor e cliente

- `server/main.py`: carrega a identidade antes de escutar, gera o salt da execução e aceita opções de endereço, porta, chave e certificado. A saída por `Ctrl+C` não mostra traceback.
- `server/connection.py`: recebe `REGISTER`, envia `HANDSHAKE` e exige `READY` autenticado. Só depois cria a sessão e envia `CLIENT_LIST`. Handshake abandonado expira após 10 segundos. Cada escrita administrativa tem prazo de 5 segundos.
- `server/sessions.py`: mantém o canal administrativo de cada conexão e limita o diretório a 128 clientes. Uma trava ordena registros, listas e saídas para evitar eventos de entrada antes da lista inicial.
- `server/relay.py`: preserva o conteúdo E2E, informa `UNKNOWN_CLIENT` sem derrubar o remetente e trata falha de escrita no destinatário. Os logs mostram apenas UUIDs e quantidade de bytes.
- `client/connection.py` e `client/messaging.py`: validam o handshake e todos os envelopes posteriores. A chave X25519 muda a cada chamada de conexão, inclusive na mesma instância. Fechar remove as referências ao material criptográfico da sessão. Novos avisos duplicados de um peer ainda ativo são recusados.
- `client/main.py`: aceita o caminho do certificado confiável e preserva os comandos de terminal entregues pelo Dev B.
- `common/protocol.py`: rejeita JSON com campos duplicados ou constantes não finitas. O limite de conteúdo do relay agora acompanha o máximo E2E de 4.164 bytes. O servidor verifica o transporte e o destino, sem interpretar nem decifrar o conteúdo E2E.
- `crypto/key_derivation.py`: o salt provisório foi removido da aplicação. Vetores fixos continuam somente em testes unitários.

A camada E2E do Dev B foi preservada: AES-128-GCM, AAD, ordem dos campos, IV base, contadores e a regra do menor UUID para selecionar A2B/B2A. Os testes anteriores foram adaptados para executar o handshake real. Não existe modo de rede sem autenticação usado pelos testes de integração.

Validação desta parte: **149 testes aprovados**, incluindo ataques ao handshake, alteração de lista após o MAC, replay administrativo nos dois sentidos, reconexão na mesma instância, rejeição de quadro de sessão anterior, salt comum por execução, ID duplicado, registros simultâneos e falha de escrita no destino. Também foi executada uma demonstração com três processos reais: servidor e dois clientes de terminal, `/peers`, mensagens nos dois sentidos, `/sair` e `Ctrl+C`. Os logs do servidor não contiveram as mensagens de teste.
