# Identidade e certificado do servidor

Execute da raiz do projeto:

```sh
.venv/bin/python -m scripts.generate_server_keys
```

O gerador cria uma chave RSA de 3072 bits em `secrets/server.key` e um certificado X.509 autoassinado em `certs/server.crt`. A validade é de 365 dias. O certificado usa SHA256 e autoassinatura PKCS#1 v1.5; as assinaturas do **handshake** usam RSA-PSS.

A chave privada é PKCS#8 PEM sem senha, protegida por permissão `0600` em sistemas POSIX. Não a envie aos clientes e não a versione. O certificado contém somente informação pública. Os caminhos padrão são locais e estão no `.gitignore`.

## Provisionamento

1. Gere a identidade na máquina do servidor.
2. Copie somente `server.crt` para cada cliente por um meio confiável.
3. Use `--certificado CAMINHO` se o cliente guardar a cópia fora de `certs/server.crt`.
4. Inicie o servidor e os clientes.

Cada cliente compara o certificado recebido com sua cópia local, em DER, e verifica a vigência e o perfil de assinatura. O servidor também confere se a chave privada corresponde ao certificado. Nenhum lado gera confiança automaticamente durante uma conexão.

## Renovação

O gerador não substitui arquivos existentes. Para renovar, gere outro par em caminhos novos:

```sh
.venv/bin/python -m scripts.generate_server_keys --chave secrets/servidor-novo.key --certificado certs/servidor-novo.crt
```

Pare o servidor, provisione o novo certificado nos clientes e inicie com `--chave secrets/servidor-novo.key --certificado certs/servidor-novo.crt`. Inicie os clientes com a cópia correspondente em `--certificado`. Retire os arquivos antigos somente depois de concluir a troca. Um cliente com o certificado anterior deve rejeitar o novo servidor.

O projeto não inclui um serviço de revogação nem uma autoridade certificadora. A confiança é a cópia exata previamente provisionada para esta aplicação acadêmica.
