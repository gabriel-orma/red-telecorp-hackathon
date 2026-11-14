"""Tiempo real del panel (E7): WebSocket API + difusor por DynamoDB Streams.

- $connect / $disconnect: registra o borra la conexión (tabla `conexiones`, TTL de 2 h).
- $default: "ping" del navegador cada ~5 min → renueva el TTL (las conexiones abandonadas caducan solas).
- difundir: escucha los streams de antenas, colectivos e incidencias y envía a cada panel un aviso liviano
  {"tipo": "antenas" | "colectivos" | "incidencias"}; el panel vuelve a pedir esos datos al API.
  Un lote de cambios genera UN aviso por tipo (no uno por registro). Conexiones que ya no existen
  (GoneException) se borran: limpieza de conexiones caídas.
"""
import json
import os
import time

import boto3
from botocore.exceptions import ClientError

from telecorp import db, util

TTL_SEGUNDOS = 2 * 3600
# Las antenas cambian varias veces por segundo durante el simulador: como mucho un aviso de cada tipo
# cada 2 s por contenedor (el panel igual vuelve a pedir el estado completo).
INTERVALO_MINIMO_S = 2.0
_ultimo_aviso: dict = {}
_api = None


def _cliente():
    global _api
    if _api is None:
        _api = boto3.client("apigatewaymanagementapi", endpoint_url=os.environ["WS_ENDPOINT"])
    return _api


def conectar(event, context):
    db.tabla("conexiones").put_item(Item={"connectionId": event["requestContext"]["connectionId"],
                                          "conectadoEn": util.ahora_iso(), "expiraEn": int(time.time()) + TTL_SEGUNDOS})
    return {"statusCode": 200}


def desconectar(event, context):
    db.tabla("conexiones").delete_item(Key={"connectionId": event["requestContext"]["connectionId"]})
    return {"statusCode": 200}


def mensaje(event, context):
    """Cualquier mensaje del cliente (ping) renueva la conexión."""
    db.tabla("conexiones").update_item(Key={"connectionId": event["requestContext"]["connectionId"]},
                                       UpdateExpression="SET expiraEn = :e", ExpressionAttributeValues={":e": int(time.time()) + TTL_SEGUNDOS})
    return {"statusCode": 200, "body": json.dumps({"tipo": "pong"})}


def _tipo(arn: str) -> str | None:
    for nombre, tipo in (("antenas", "antenas"), ("colectivos", "colectivos"), ("incidencias", "incidencias")):
        if f"-{nombre}/stream/" in arn:
            return tipo
    return None


def difundir(event, context):
    ahora = time.time()
    tipos = sorted({t for r in event.get("Records", []) if (t := _tipo(r.get("eventSourceARN", "")))
                    and (t != "antenas" or ahora - _ultimo_aviso.get(t, 0) >= INTERVALO_MINIMO_S)})
    for t in tipos:
        _ultimo_aviso[t] = ahora
    if not tipos:
        return {"enviados": 0}
    conexiones = db.scan_todo(db.tabla("conexiones"), ProjectionExpression="connectionId")
    enviados, borradas = 0, 0
    for c in conexiones:
        for tipo in tipos:
            try:
                _cliente().post_to_connection(ConnectionId=c["connectionId"],
                                              Data=json.dumps({"tipo": tipo, "en": util.ahora_iso()}).encode())
                enviados += 1
            except ClientError as e:
                if e.response["Error"]["Code"] in ("GoneException", "410"):
                    db.tabla("conexiones").delete_item(Key={"connectionId": c["connectionId"]})
                    borradas += 1
                    break
                raise
    return {"tipos": tipos, "conexiones": len(conexiones), "enviados": enviados, "borradas": borradas}
