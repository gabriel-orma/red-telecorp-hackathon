"""Notificaciones a usuarios afectados (E3).

Canales disponibles en Learner Lab (ver D1: SES y SMS bloqueados):
1. **En la app**: cada aviso queda como evento NOTIFICACION_ENVIADA en el historial de la incidencia;
   el portal de seguimiento lo muestra como mensaje.
2. **Email vía SNS**: se publica en el tópico `avisos` con el atributo `usuarioId`; solo lo reciben los usuarios
   que aceptaron avisos por correo (suscripción con FilterPolicy por usuarioId, confirmada por ellos).
"""
import json
import os

import boto3

from telecorp import historial, zonas

_sns = boto3.client("sns")

MENSAJES = {
    "EN_EVALUACION": ("Estamos evaluando un posible problema en tu zona",
                      "Recibimos varios reportes en {zona}. Nuestro equipo está verificando la red de la zona; "
                      "te avisaremos apenas tengamos novedades."),
    "INCIDENCIA_CONFIRMADA": ("Identificamos una incidencia en tu zona",
                              "Confirmamos una falla que afecta el servicio en {zona}. Un equipo técnico ya está "
                              "trabajando para restablecerlo."),
    "SERVICIO_RESTABLECIDO": ("El servicio en tu zona fue restablecido",
                              "El servicio en {zona} ya fue restablecido. Si sigues con problemas, reinicia tu equipo "
                              "o vuelve a reportarlo. ¡Gracias por tu paciencia!"),
}


def mensaje(estado: str, zona_id: str) -> tuple[str, str]:
    asunto, cuerpo = MENSAJES[estado]
    nombre = (zonas.zona(zona_id) or {}).get("nombre", zona_id)
    return asunto, cuerpo.format(zona=nombre)


def notificar(incidencia: dict, estado_colectivo: str, colectivo_id: str) -> dict:
    """Avisa a un usuario. Devuelve el resultado por canal (y siempre lo deja en el historial)."""
    asunto, cuerpo = mensaje(estado_colectivo, incidencia["zonaId"])
    canales = {"app": "ok"}
    topico = os.environ.get("TOPICO_AVISOS")
    if topico:
        try:
            _sns.publish(
                TopicArn=topico, Subject=f"Red TeleCorp: {asunto}"[:100], Message=cuerpo,
                MessageAttributes={"usuarioId": {"DataType": "String", "StringValue": incidencia["usuarioId"]}},
            )
            canales["email"] = "publicado"  # entregado solo si el usuario confirmó su suscripción
        except Exception as e:  # noqa: BLE001 - un canal caído no detiene los demás
            canales["email"] = f"error: {type(e).__name__}"
    historial.registrar(
        incidencia["incidenciaId"], "INCIDENCIA", "NOTIFICACION_ENVIADA", "STEP_FUNCTION",
        detalle=json.dumps({"asunto": asunto, "mensaje": cuerpo, "canales": canales,
                            "colectivo": colectivo_id, "estado": estado_colectivo}, ensure_ascii=False),
    )
    return canales


def suscribir_email(email: str, usuario_id: str) -> str | None:
    """Suscribe el correo al tópico de avisos filtrando por usuario. AWS envía un correo de confirmación."""
    topico = os.environ.get("TOPICO_AVISOS")
    if not (topico and email):
        return None
    r = _sns.subscribe(TopicArn=topico, Protocol="email", Endpoint=email, ReturnSubscriptionArn=True,
                       Attributes={"FilterPolicy": json.dumps({"usuarioId": [usuario_id]})})
    return r.get("SubscriptionArn")
