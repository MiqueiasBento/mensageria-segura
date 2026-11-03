"""Encaminha bytes opacos e mantém o remetente conectado se o destino sair."""

from src.common.protocol import ErroProtocolo, decodificar_conteudo, validar_id_cliente


async def encaminhar(mensagem, remetente, sessoes, enviar):
    id_destinatario = validar_id_cliente(mensagem.get("recipient_id"))
    if id_destinatario == remetente.id_cliente:
        raise ErroProtocolo("destino não pode ser o próprio remetente")
    conteudo = decodificar_conteudo(mensagem.get("payload"))
    destinatario = sessoes.obter_cliente(id_destinatario)
    if destinatario is None:
        await enviar(remetente, {"type": "ERROR", "code": "UNKNOWN_CLIENT"})
        return
    try:
        await enviar(destinatario, {
            "type": "RELAY", "sender_id": remetente.id_cliente,
            "recipient_id": id_destinatario, "payload": mensagem["payload"],
        })
    except (ConnectionError, OSError, TimeoutError):
        destinatario.escritor.close()
        await enviar(remetente, {"type": "ERROR", "code": "UNKNOWN_CLIENT"})
        return
    print(f"Relay: origem={remetente.id_cliente} destino={id_destinatario} bytes={len(conteudo)}")
