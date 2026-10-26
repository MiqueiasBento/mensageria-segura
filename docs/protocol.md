# Protocolo de Comunicação --- Mensageria Segura Multi-Cliente

> **Status:** versão inicial para orientar a implementação.\
> **Base:** especificação do Trabalho Prático 3.\
> **Atenção:** os pontos marcados como **PENDENTE** precisam ser
> confirmados ou decididos antes da implementação da etapa
> correspondente. Este documento não substitui o enunciado do professor.

## 1. Objetivo e arquitetura

O sistema utiliza conexões TCP entre clientes e um servidor central. O
servidor atua como ponto de registro e encaminhamento (*relay*): recebe
conexões, mantém informações temporárias das sessões, distribui chaves
públicas e encaminha quadros entre clientes.

As mensagens de aplicação entre clientes devem ser protegidas ponta a
ponta. O servidor encaminha o conteúdo criptografado e não deve possuir
as chaves necessárias para descriptografá-lo.

``` text
Cliente A  <-- TCP -->  Servidor relay  <-- TCP -->  Cliente B
    |                         |                         |
    +------ mensagem E2E criptografada ----------------+
```

**Escolha recomendada:** TCP, sem FastAPI ou Spring Boot. O trabalho
define um protocolo próprio sobre TCP; um framework HTTP não é
necessário para cumprir esse fluxo e acrescentaria uma camada que não
resolve os requisitos centrais.

## 2. Convenções gerais

-   Transporte: TCP.
-   Inteiro de tamanho de quadro: unsigned, 4 bytes, big-endian.
-   UUID de cliente: UUIDv4 em representação binária de 16 bytes.
-   Chaves públicas X25519: 32 bytes no formato raw.
-   Salt: 16 bytes.
-   Nonce AES-GCM: 12 bytes.
-   Tag AES-GCM: 16 bytes.
-   Tamanho máximo do texto claro: 4096 bytes.
-   Contadores `seq_no`: 8 bytes, big-endian.
-   O servidor não descriptografa mensagens E2E.

Os nomes de campos abaixo são nomes lógicos. A serialização concreta dos
corpos de controle (por exemplo, JSON ou formato binário) ainda precisa
ser definida na seção 10.

## 3. Enquadramento TCP (framing)

TCP é um fluxo de bytes e não preserva fronteiras de mensagens.
Portanto, cada mensagem de aplicação será enquadrada com um prefixo de
tamanho:

``` text
+----------------------+-----------------------------+
| tamanho (4 bytes)    | corpo (tamanho bytes)       |
+----------------------+-----------------------------+
```

-   O prefixo contém o tamanho do corpo, não inclui os próprios 4 bytes
    do prefixo.
-   O valor é codificado em big-endian.
-   O receptor deve primeiro ler exatamente 4 bytes; em seguida, deve
    ler exatamente a quantidade indicada.
-   Se o tamanho for inválido ou exceder o limite definido para o
    quadro, a conexão deve ser encerrada com segurança.
-   O limite de 4096 bytes do enunciado refere-se ao texto claro.
    **PENDENTE:** definir o limite máximo do corpo/quadro de transporte,
    que será maior devido aos cabeçalhos e à criptografia.

**Por que usar framing:** uma chamada de `send` não corresponde
necessariamente a uma única chamada de `recv`. O prefixo permite
reconstruir cada mensagem mesmo quando o TCP entrega os bytes em blocos
diferentes.

## 4. Mensagens de controle

O servidor precisa distinguir mensagens de controle de quadros E2E
encaminhados. Recomenda-se que cada corpo de controle comece com um
campo `type`, seguido dos campos específicos daquele tipo.

### 4.1 `REGISTER` --- registro do cliente

**Direção:** cliente → servidor.

Campos lógicos:

  Campo                 Descrição
  --------------------- ----------------------------------------
  `type`                `REGISTER`
  `client_id`           UUIDv4 do cliente, 16 bytes
  `client_public_key`   Chave pública efêmera X25519, 32 bytes

Finalidade: registrar o cliente na sessão atual e permitir que o
servidor distribua sua chave pública aos demais clientes.

**PENDENTE:** confirmar no enunciado/professor se o registro deve conter
outros campos ou se a chave efêmera é renovada a cada conexão.

### 4.2 `CLIENT_JOINED` --- divulgação de novo cliente

**Direção:** servidor → clientes já conectados.

Campos lógicos:

  Campo                 Descrição
  --------------------- --------------------------------------
  `type`                `CLIENT_JOINED`
  `client_id`           UUIDv4 do novo cliente
  `client_public_key`   Chave pública X25519 do novo cliente

Finalidade: informar aos clientes existentes sobre a entrada de um novo
participante.

### 4.3 `CLIENT_LIST` --- lista de clientes ativos

**Direção:** servidor → cliente recém-registrado.

Campos lógicos:

  -----------------------------------------------------------------------
  Campo                               Descrição
  ----------------------------------- -----------------------------------
  `type`                              `CLIENT_LIST`

  `clients`                           Lista de pares `client_id` e
                                      `client_public_key` dos clientes
                                      ativos
  -----------------------------------------------------------------------

Finalidade: permitir que o cliente recém-conectado conheça os
participantes com quem poderá estabelecer comunicação E2E.

### 4.4 `RELAY` --- encaminhamento de quadro E2E

**Direção:** cliente remetente → servidor → cliente destinatário.

O servidor deve encaminhar os bytes do quadro E2E sem descriptografar ou
modificar o conteúdo criptografado.

O quadro E2E tem o formato definido na seção 5. O servidor pode usar os
identificadores de remetente e destinatário para localizar a sessão de
destino.

**PENDENTE:** definir se o quadro E2E será enviado diretamente como
corpo do frame TCP ou encapsulado em uma mensagem de controle `RELAY`. A
opção mais simples é encaminhar o quadro E2E como corpo do frame, pois
seu cabeçalho já contém `sender_id` e `recipient_id`. Nesse caso, o tipo
de mensagem precisa ser distinguível sem ambiguidade das mensagens de
controle.

### 4.5 `ERROR` --- erro de protocolo

**Direção:** servidor → cliente (e, quando aplicável, cliente →
servidor).

Campos lógicos recomendados:

  Campo           Descrição
  --------------- -----------------------------------------
  `type`          `ERROR`
  `code`          Código curto e estável do erro
  `description`   Descrição não sensível para diagnóstico

Exemplos de códigos: `INVALID_FRAME`, `UNKNOWN_CLIENT`,
`INVALID_MESSAGE`, `UNAUTHORIZED`.

O erro não deve incluir chaves privadas, segredo compartilhado, salt em
claro em logs ou conteúdo de mensagens.

### 4.6 `DISCONNECT` --- encerramento explícito (opcional)

**Direção:** cliente → servidor.

Pode ser usado para sinalizar encerramento voluntário. O fechamento TCP
também deve ser tratado como desconexão.

**PENDENTE:** confirmar se o professor exige uma mensagem explícita de
encerramento. Se não exigir, o fechamento da conexão TCP pode ser
suficiente.

## 5. Formato do quadro E2E

O quadro encaminhado entre clientes possui os seguintes campos, na ordem
indicada pelo enunciado:

``` text
+-------------+------------+--------------+------------+------------------+
| nonce       | sender_id  | recipient_id | seq_no     | ciphertext + tag|
| 12 bytes    | 16 bytes   | 16 bytes     | 8 bytes    | variável         |
+-------------+------------+--------------+------------+------------------+
```

-   `nonce`: 12 bytes.
-   `sender_id`: UUID binário de 16 bytes.
-   `recipient_id`: UUID binário de 16 bytes.
-   `seq_no`: contador de 8 bytes, big-endian.
-   `ciphertext + tag`: texto cifrado seguido da tag GCM de 16 bytes.

O texto claro não pode exceder 4096 bytes.

### 5.1 AAD

O AAD usado no AES-GCM é:

``` text
sender_id || recipient_id || seq_no
```

Esses campos são autenticados, mas não criptografados. Alterações neles
devem fazer a verificação da tag falhar.

### 5.2 Nonce

O nonce de cada direção é formado por:

``` text
IV_base (4 bytes) || seq_no (8 bytes, big-endian)
```

Cada direção da comunicação deve ter seu próprio `IV_base` aleatório de
4 bytes. O contador não pode ser reutilizado com a mesma chave.

### 5.3 Chaves direcionais

Para cada par de clientes, são derivadas chaves distintas por direção:

-   `Key_A2B`: usada por A para enviar a B e por B para receber de A.
-   `Key_B2A`: usada por B para enviar a A e por A para receber de B.

Isso separa o tráfego nos dois sentidos e evita reutilizar a mesma chave
nos dois fluxos.

## 6. Estabelecimento de chaves e autenticação

O fluxo criptográfico descrito no enunciado envolve:

1.  Clientes geram chaves efêmeras X25519; a chave privada permanece
    local.
2.  Clientes obtêm do servidor as chaves públicas efêmeras dos demais
    participantes.
3.  Cada par de clientes calcula o segredo compartilhado por X25519.
4.  O segredo compartilhado é usado como IKM na derivação HKDF-SHA256.
5.  HKDF-Extract usa `salt_srv` como salt.
6.  HKDF-Expand deriva chaves de 16 bytes com os rótulos `A2B` e `B2A`.
7.  O servidor usa RSA-PSS para autenticação conforme o mecanismo
    indicado no enunciado.

Forma indicada para ECDH:

``` text
Z_AB = ECDH(sk_A, pk_B)
```

Derivação indicada:

``` text
PRK      = HKDF-Extract(salt=salt_srv, IKM=Z_AB)
Key_A2B  = HKDF-Expand(PRK, info="A2B", L=16)
Key_B2A  = HKDF-Expand(PRK, info="B2A", L=16)
```

**PENDENTE --- ambiguidade do enunciado:** a descrição geral menciona
assinatura de uma chave efêmera ECDHE, mas a fórmula detalhada apresenta
`pk_server || pk_client || client_id || salt`. É necessário confirmar
com o professor o significado exato de `pk_server` e qual chave pública
deve ser assinada. Não implementar essa parte por suposição.

**PENDENTE --- distribuição do salt:** confirmar como `salt_srv` é
compartilhado entre os dois clientes de cada par, para que ambos usem o
mesmo valor na derivação das mesmas chaves direcionais.

## 7. Controle de sequência e proteção contra replay

Estado por par/direção:

  Variável       Estado inicial Regra
  ------------ ---------------- ---------------------------
  `seq_send`                `0` Próximo contador a enviar
  `seq_recv`               `-1` Último contador aceito

Ao enviar: 1. Usar o valor atual de `seq_send`. 2. Construir o nonce com
`IV_base_send || seq_send`. 3. Criptografar e enviar o quadro. 4.
Incrementar `seq_send` após a construção/envio conforme a política de
falhas definida na implementação.

Ao receber: 1. Ler o `seq_no`. 2. Rejeitar se não for estritamente maior
que `seq_recv`. 3. Verificar a tag AES-GCM. 4. Atualizar `seq_recv`
somente após autenticação bem-sucedida e aceitação da mensagem.

**Importante:** a verificação de sequência não substitui a autenticação
GCM. A mensagem só deve ser aceita depois de passar por ambas as
verificações.

**PENDENTE:** o enunciado indica rejeição de replay pelo destinatário ou
pelo servidor se o contador fizer parte do protocolo de roteamento. A
opção recomendada é o destinatário validar `seq_no`, pois o servidor não
deve precisar conhecer as chaves E2E.

## 8. Estado mantido pelo servidor e pelos clientes

### 8.1 Servidor

Para cada conexão/sessão, o servidor mantém, no mínimo, os dados
necessários para encaminhamento e controle:

-   writer/conexão TCP;
-   `client_id`;
-   chave pública do cliente;
-   estado de sequência para mensagens administrativas do servidor, se
    aplicável.

O enunciado descreve `seq_send` para mensagens administrativas do
servidor e `seq_recv` para controle de recebimento. **PENDENTE:**
especificar quais mensagens administrativas usam esses contadores e como
são autenticadas/formatadas, pois não devem ser confundidas com os
quadros E2E.

### 8.2 Cliente

Para cada peer, o cliente mantém:

-   `peer_public_key`;
-   segredo compartilhado `Z` (somente em memória, nunca em logs);
-   `key_send` e `key_recv`;
-   `seq_send` e `seq_recv`;
-   `IV_base_send` e `IV_base_recv`.

As chaves privadas efêmeras permanecem no cliente.

## 9. Desconexão e reconexão

-   Ao desconectar, o servidor remove a sessão da memória e informa os
    demais clientes, se o protocolo exigir.
-   Ao reconectar, o cliente deve realizar um novo handshake.
-   Devem ser geradas novas chaves efêmeras e novas chaves E2E.
-   Não reutilizar salt, chaves, IV bases ou contadores de uma sessão
    anterior.

## 10. Decisões pendentes antes de fechar o protocolo

As escolhas abaixo são recomendadas para a implementação, mas precisam
ser confirmadas/fechadas pela dupla. As ambiguidades do enunciado devem
ser esclarecidas com o professor.

  -----------------------------------------------------------------------
  Decisão                 Recomendação inicial    Situação
  ----------------------- ----------------------- -----------------------
  Linguagem               Python                  Escolha da dupla

  Comunicação             TCP                     Definido pela dupla

  Framework               Sem framework web;      Recomendado
                          `asyncio`               

  Biblioteca              Python `cryptography`   Recomendado; confirmar
  criptográfica                                   restrições do professor

  Serialização das        JSON UTF-8 dentro do    Pendente de aprovação
  mensagens de controle   frame TCP, com bytes    da dupla
                          binários codificados em 
                          Base64                  

  Identificação de        Campo `type` nas        Recomendado
  mensagens               mensagens de controle   

  Separação controle/E2E  Definir um              Pendente
                          envelope/tipo           
                          inequívoco para         
                          distinguir os dois      

  Limite máximo do corpo  Definir limite acima do Pendente
  TCP                     máximo do texto claro   
                          de 4096 bytes           

  `salt_srv`              Mesmo salt para ambos   Confirmar mecanismo com
                          os lados de cada        professor
                          par/sessão              

  Chave assinada por      Não presumir;           Aguardando professor
  RSA-PSS                 esclarecer `pk_server`  

  Mensagem explícita de   Opcional; fechamento    Pendente
  desconexão              TCP é obrigatório       
                          tratar                  

  Erros e códigos         Definir códigos mínimos Pendente
                          e comportamento de      
                          encerramento            
  -----------------------------------------------------------------------

### Proposta de serialização para mensagens de controle

Para facilitar a implementação e depuração, recomenda-se JSON UTF-8 como
corpo das mensagens de controle. Campos binários seriam codificados em
Base64. Exemplo ilustrativo:

``` json
{
  "type": "REGISTER",
  "client_id": "UUID-EM-FORMATO-TEXTO",
  "client_public_key": "BASE64_DA_CHAVE_PUBLICA"
}
```

Essa representação é uma conveniência de implementação, não um formato
exigido pelo enunciado. O quadro E2E deve continuar em formato binário,
conforme a estrutura especificada.

## 11. Sequência recomendada de implementação

1.  Implementar leitura/escrita de frames TCP com prefixo de 4 bytes.
2.  Definir e implementar serialização das mensagens de controle.
3.  Fazer dois clientes conectarem, registrarem-se e receberem a lista
    de peers.
4.  Implementar encaminhamento de um quadro de teste sem criptografia,
    apenas para validar o relay.
5.  Implementar e testar geração de chaves X25519 e ECDH.
6.  Implementar HKDF e verificar que os dois clientes derivam as mesmas
    chaves direcionais.
7.  Implementar RSA-PSS conforme esclarecimento do professor.
8.  Integrar AES-GCM, AAD, nonce e contadores.
9.  Implementar rejeição de replay, alteração de conteúdo e quadros
    malformados.
10. Testar desconexão, reconexão e geração de novas chaves.

## 12. Testes mínimos previstos

-   Dois ou mais clientes conseguem se registrar.
-   Clientes recebem as chaves públicas dos peers.
-   Dois clientes derivam chaves compatíveis e trocam mensagens E2E.
-   O servidor encaminha os bytes sem descriptografar.
-   Alteração de um bit no quadro é rejeitada pela autenticação GCM.
-   Reenvio de um `seq_no` já aceito é rejeitado.
-   Quadro com tamanho inválido ou excessivo causa tratamento seguro e
    desconexão.
-   Reconexão gera novo material criptográfico e não reutiliza estado da
    sessão anterior.

## 13. Regras de segurança operacional

-   Nunca registrar chaves privadas, segredo compartilhado `Z`, conteúdo
    de mensagens ou material secreto em logs.
-   Não reutilizar nonce com a mesma chave AES-GCM.
-   Não aceitar mensagem antes de validar autenticação e sequência.
-   Não confiar em identificadores recebidos sem validar o estado da
    sessão.
-   O servidor deve encaminhar mensagens E2E sem tentar
    descriptografá-las.
-   A chave pública RSA do servidor deve ser autenticada por meio do
    certificado provisionado conforme o enunciado; não aceitar
    silenciosamente uma chave apresentada por uma conexão não
    autenticada.
