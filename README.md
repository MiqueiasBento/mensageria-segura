# Mensageria Segura | Segurança de Software

Trabalho prático 3 de Segurança de Software — Prof. Michel Sales.

## Executar a etapa inicial

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m src.server.main
```

O servidor escuta em `127.0.0.1:8000`. Para executar os testes:

```sh
.venv/bin/python -m pytest -q tests/test_initial_server.py
```

O contrato de mensagens e as decisões desta fase estão em [docs/anotacoes/etapa-inicial.md](docs/anotacoes/etapa-inicial.md). O relay atual é apenas para dados de teste: a proteção criptográfica ainda será integrada.
