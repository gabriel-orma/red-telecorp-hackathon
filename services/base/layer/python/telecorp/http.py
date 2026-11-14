"""Respuestas JSON para el HTTP API."""
import json

from telecorp import util


def respuesta(status: int, cuerpo) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json; charset=utf-8", "cache-control": "no-store"},
        "body": json.dumps(util.desde_dynamo(cuerpo), ensure_ascii=False),
    }


def ok(cuerpo) -> dict:
    return respuesta(200, cuerpo)


def error(status: int, mensaje: str, **extra) -> dict:
    return respuesta(status, {"error": mensaje, **extra})


def cuerpo_json(event) -> dict:
    import base64
    texto = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        texto = base64.b64decode(texto).decode("utf-8")
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError:
        raise ValueError("El cuerpo no es JSON válido")
    if not isinstance(datos, dict):
        raise ValueError("El cuerpo debe ser un objeto JSON")
    return datos
