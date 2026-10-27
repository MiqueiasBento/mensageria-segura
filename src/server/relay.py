"""Encaminha conteúdo opaco sem interpretar os seus bytes."""

from src.common.protocol import ErroProtocolo, decodificar_conteudo, validar_id_cliente


async def encaminhar(mensagem, remetente, sessoes, enviar):
    id_destinatario = validar_id_cliente(mensagem.get("recipient_id"))
    if id_destinatario == remetente.id_cliente:
        raise ErroProtocolo("cannot relay to self")
    destinatario = sessoes.obter_cliente(id_destinatario)
    if destinatario is None:
        raise ErroProtocolo("unknown recipient")
    decodificar_conteudo(mensagem.get("payload"))
    await enviar(destinatario, {
        "type": "RELAY",
        "sender_id": remetente.id_cliente,
        "recipient_id": id_destinatario,
        "payload": mensagem["payload"],
    })
