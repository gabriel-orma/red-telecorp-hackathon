"""Clasificador de métricas (SQS → DynamoDB).

Por cada métrica:
1. Clasifica el estado (0 / <60 / 60–129 / >129).
2. Guarda la lectura en `metricas` (con TTL).
3. Actualiza el estado actual en `antenas` (ignora lecturas más viejas que la última).
4. Si el estado cambió, registra CAMBIO_ESTADO en el historial (lo usarán la detección y la recurrencia).
"""
import json
import time

from botocore.exceptions import ClientError

from telecorp import db, historial, reglas, util

TTL_METRICAS_DIAS = 7


def procesar(m: dict) -> dict:
    gb = float(m["gbPorMinuto"])
    estado = reglas.clasificar_antena(gb)
    medido_en = m["medidoEn"]
    metrica = {**m, "gbPorMinuto": gb, "estado": estado}

    db.tabla("metricas").put_item(Item=util.a_dynamo({
        **metrica, "expiraEn": int(time.time()) + TTL_METRICAS_DIAS * 86400,
    }))

    antenas = db.tabla("antenas")
    try:
        anterior = antenas.update_item(
            Key={"antenaId": m["antenaId"]},
            UpdateExpression="SET zonaId = :z, estado = :e, gbPorMinuto = :gb, actualizadoEn = :t, "
                             "estadoDesde = if_not_exists(estadoDesde, :t)",
            ConditionExpression="attribute_not_exists(actualizadoEn) OR actualizadoEn < :t",
            ExpressionAttributeValues=util.a_dynamo({":z": m["zonaId"], ":e": estado, ":gb": gb, ":t": medido_en}),
            ReturnValues="ALL_OLD",
        ).get("Attributes", {})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return {**metrica, "ignorada": "lectura más vieja que el estado actual"}
        raise

    estado_anterior = anterior.get("estado")
    if estado_anterior != estado:
        antenas.update_item(Key={"antenaId": m["antenaId"]}, UpdateExpression="SET estadoDesde = :t",
                            ExpressionAttributeValues={":t": medido_en})
        historial.registrar(
            m["antenaId"], "ANTENA", "CAMBIO_ESTADO", "SISTEMA",
            detalle=f"{gb} GB/min → {estado}", estado_anterior=estado_anterior, estado_nuevo=estado,
            ocurrido_en=medido_en,
        )
    return metrica


def handler(event, context):
    """Respuesta parcial: solo se reintentan (y van a la DLQ) los mensajes que fallan."""
    fallidos = []
    for r in event.get("Records", []):
        try:
            procesar(json.loads(r["body"]))
        except Exception as e:  # noqa: BLE001 - se registra y el mensaje vuelve a la cola
            print(f"ERROR métrica {r.get('messageId')}: {e!r}")
            fallidos.append({"itemIdentifier": r["messageId"]})
    return {"batchItemFailures": fallidos}
