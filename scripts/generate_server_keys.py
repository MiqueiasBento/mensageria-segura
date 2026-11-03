"""Execute da raiz: python -m scripts.generate_server_keys."""

import argparse
from src.crypto.identity import (
    CAMINHO_CERTIFICADO, CAMINHO_CHAVE, gerar_identidade, salvar_identidade,
)


def principal():
    argumentos = argparse.ArgumentParser(description="Gerar identidade RSA do servidor")
    argumentos.add_argument("--chave", default=str(CAMINHO_CHAVE))
    argumentos.add_argument("--certificado", default=str(CAMINHO_CERTIFICADO))
    opcoes = argumentos.parse_args()
    try:
        salvar_identidade(gerar_identidade(), opcoes.chave, opcoes.certificado)
    except (OSError, ValueError) as erro:
        argumentos.exit(1, f"Não foi possível gerar a identidade: {erro}\n")
    print(f"Identidade criada. Provisione somente {opcoes.certificado} nos clientes.")


if __name__ == "__main__":
    principal()
