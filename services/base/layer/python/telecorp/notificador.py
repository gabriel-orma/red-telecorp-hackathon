"""Notificaciones a usuarios afectados (E3).

Canales disponibles en Learner Lab (ver D1: SES y SMS bloqueados):
1. **En la app**: cada aviso queda como evento NOTIFICACION_ENVIADA en el historial de la incidencia;
   el portal de seguimiento lo muestra como mensaje.
2. **Email vía Azure Communication Services** (2.ª nube): solo para quien aceptó avisos por correo y nunca para reportes
   simulados ni dominios reservados; con el límite por hora de ACS. Si envía, no se duplica por SNS.
3. **Email vía SNS** (respaldo): se publica en el tópico `avisos` con el atributo `usuarioId`; solo lo reciben los usuarios
   que aceptaron avisos por correo (suscripción con FilterPolicy por usuarioId, confirmada por ellos).
"""
import json
import os
import time

import boto3
from botocore.exceptions import ClientError

from telecorp import db, historial, zonas

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
    # Verificación de red SIN falla (H03): nunca se dice "falla confirmada" si las antenas de la zona están bien.
    # No es un estado del colectivo: solo un tipo de aviso del flujo (el colectivo sigue EN_EVALUACION).
    "SIN_FALLA_RED": ("Seguimos evaluando el problema en tu zona",
                      "Revisamos las antenas de {zona} y por ahora no muestran fallas. Seguimos analizando los reportes "
                      "de tus vecinos y te avisaremos apenas haya novedades. Si tu servicio sigue mal, reinicia tu equipo."),
}

AVISO_TTL_DIAS = 7
AVISO_VIGENCIA_SEG = 180   # un aviso "ENVIANDO" más viejo que esto se considera caído y puede reintentarse


def _reclamar_aviso(incidencia_id: str, estado: str) -> int | None:
    """Idempotencia (H32): marca condicional en `dedup` ANTES de enviar. Devuelve la marca si ganó; None si otro ya avisó
    (o está avisando). Un reintento tras un envío completo no duplica el correo, el historial ni los contadores."""
    ahora = int(time.time())
    try:
        db.tabla("dedup").put_item(
            Item={"clave": f"AVISO#{incidencia_id}#{estado}", "incidenciaId": incidencia_id, "fase": "ENVIANDO",
                  "ts": ahora, "expiraEn": ahora + AVISO_TTL_DIAS * 86400},
            ConditionExpression="attribute_not_exists(clave) OR (fase = :env AND ts < :viejo)",
            ExpressionAttributeValues={":env": "ENVIANDO", ":viejo": ahora - AVISO_VIGENCIA_SEG})
        return ahora
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise


def _confirmar_aviso(incidencia_id: str, estado: str, marca: int) -> None:
    """ENVIADO es definitivo. Si esta escritura falla el aviso YA salió: no se relanza (solo quedaría 'ENVIANDO')."""
    try:
        db.tabla("dedup").update_item(
            Key={"clave": f"AVISO#{incidencia_id}#{estado}"}, UpdateExpression="SET fase = :ok",
            ConditionExpression="ts = :m", ExpressionAttributeValues={":ok": "ENVIADO", ":m": marca})
    except ClientError:
        pass


def _soltar_aviso(incidencia_id: str, estado: str, marca: int) -> None:
    """Si el envío falló, se libera la marca para que el reintento sí envíe (sin esto el aviso se perdería)."""
    try:
        db.tabla("dedup").delete_item(Key={"clave": f"AVISO#{incidencia_id}#{estado}"},
                                      ConditionExpression="ts = :m", ExpressionAttributeValues={":m": marca})
    except ClientError:
        pass


def mensaje(estado: str, zona_id: str) -> tuple[str, str]:
    asunto, cuerpo = MENSAJES[estado]
    nombre = (zonas.zona(zona_id) or {}).get("nombre", zona_id)
    return asunto, cuerpo.format(zona=nombre)


def notificar(incidencia: dict, estado_colectivo: str, colectivo_id: str) -> dict:
    """Avisa a un usuario UNA sola vez por (incidencia, estado). Devuelve el resultado por canal; si ya se había avisado
    (reintento de Step Functions, o el usuario ya recibió el aviso al sumarse al colectivo) devuelve {"omitido": ...}."""
    marca = _reclamar_aviso(incidencia["incidenciaId"], estado_colectivo)
    if marca is None:
        return {"omitido": "ya avisado"}
    try:
        asunto, cuerpo = mensaje(estado_colectivo, incidencia["zonaId"])
        canales = {"app": "ok"}
        extra: dict = {}
        azure = _correo_azure(incidencia.get("reporte") or {}, asunto, cuerpo, extra)
        if azure is not None:
            canales["azureEmail"] = azure
        if extra.get("operacion"):
            canales["azureOperacion"] = extra["operacion"]   # id de ACS: permite comprobar la entrega (Succeeded/Failed)
        topico = os.environ.get("TOPICO_AVISOS")
        if azure == "enviado":
            canales["email"] = "omitido: ya enviado por Azure"   # evita duplicar el correo por SNS
        elif topico:
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
    except Exception:
        _soltar_aviso(incidencia["incidenciaId"], estado_colectivo, marca)  # que el reintento sí envíe
        raise
    _confirmar_aviso(incidencia["incidenciaId"], estado_colectivo, marca)
    return canales


def _correo_azure(reporte: dict, asunto: str, cuerpo: str, extra: dict | None = None) -> str | None:
    """Canal ACS. None = no aplica (sin consentimiento, simulado o sin correo). Nunca lanza.
    Si se pasa `extra`, se le añade `operacion` (id de la operación de ACS) cuando el envío fue aceptado."""
    email = reporte.get("email")
    if not (reporte.get("avisarPorEmail") and email) or reporte.get("simulado"):
        return None
    try:
        from html import escape
        from telecorp.nube2 import azure_acs
        r = azure_acs.enviar_correo(email, f"Red TeleCorp: {asunto}", cuerpo,
                                    html=f"<p>{escape(cuerpo)}</p><p><small>Red TeleCorp · aviso automático</small></p>")
        if r.get("enviado") and extra is not None and r.get("operationId"):
            extra["operacion"] = r["operationId"]
        return "enviado" if r.get("enviado") else f"no enviado: {r.get('motivo')}"
    except Exception as e:  # noqa: BLE001 - un canal caído no detiene los demás
        return f"error: {type(e).__name__}"


def suscribir_email(email: str, usuario_id: str) -> str | None:
    """Suscribe el correo al tópico de avisos filtrando por usuario. AWS envía un correo de confirmación."""
    topico = os.environ.get("TOPICO_AVISOS")
    if not (topico and email):
        return None
    r = _sns.subscribe(TopicArn=topico, Protocol="email", Endpoint=email, ReturnSubscriptionArn=True,
                       Attributes={"FilterPolicy": json.dumps({"usuarioId": [usuario_id]})})
    return r.get("SubscriptionArn")
