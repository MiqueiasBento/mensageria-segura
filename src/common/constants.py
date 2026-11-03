"""Tamanhos fixos do protocolo, em bytes, compartilhados por cliente e servidor."""

TAMANHO_ID = 16                 # UUIDv4 binario
TAMANHO_CHAVE_PUBLICA = 32      # X25519 raw
TAMANHO_SALT = 16
TAMANHO_NONCE = 12              # IV_base || seq_no
TAMANHO_IV_BASE = 4
TAMANHO_SEQ = 8                 # unsigned, big-endian
TAMANHO_TAG = 16                # tag do AES-GCM
TAMANHO_CHAVE_AES = 16          # AES-128
MAX_TEXTO_CLARO = 4096

# nonce | sender_id | recipient_id | seq_no
TAMANHO_CABECALHO_E2E = TAMANHO_NONCE + 2 * TAMANHO_ID + TAMANHO_SEQ
TAMANHO_MINIMO_QUADRO_E2E = TAMANHO_CABECALHO_E2E + TAMANHO_TAG
TAMANHO_MAXIMO_QUADRO_E2E = TAMANHO_MINIMO_QUADRO_E2E + MAX_TEXTO_CLARO
