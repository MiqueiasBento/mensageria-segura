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
