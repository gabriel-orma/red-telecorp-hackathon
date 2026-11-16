"""Clasificador de métricas (SQS → DynamoDB).

Por cada métrica:
1. Clasifica el estado (0 / <60 / 60–129 / >129).
2. Guarda la lectura en `metricas` (con TTL).
3. Actualiza el estado actual en `antenas` con UNA sola escritura condicional (ignora lecturas más viejas que la última).
   La escritura única deja `estadoDesde` correcto en la imagen que ve el stream de la transición (H14), y registra
   `estadoAnterior` y `cambioEn` para que un reintento pueda completar el historial (H17).
4. Si el estado cambió, registra CAMBIO_ESTADO en el historial con clave determinista: es idempotente, y si el proceso
   murió entre (3) y (4) el reintento de SQS lo completa en lugar de ignorarlo.
"""
import json
import time

from botocore.exceptions import ClientError

from telecorp import db, historial, reglas, util

TTL_METRICAS_DIAS = 7
INTENTOS = 5


def _registrar_cambio(antena_id: str, gb: float, estado: str, anterior, medido_en: str, simulada: bool = False) -> None:
    try:
        historial.registrar(
            antena_id, "ANTENA", "CAMBIO_ESTADO", "SISTEMA",
            detalle=f"{gb} GB/min → {estado}" + (" (simulado)" if simulada else ""), estado_anterior=anterior,
            estado_nuevo=estado, ocurrido_en=medido_en, token="cambio",  # determinista: reintentar no duplica el evento
            simulado=simulada,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def procesar(m: dict) -> dict:
    gb = float(m["gbPorMinuto"])
    estado = reglas.clasificar_antena(gb)
    medido_en = m["medidoEn"]
    simulada = bool(m.get("simulada"))   # la pone el simulador solo en lecturas de fallas forzadas
    metrica = {**m, "gbPorMinuto": gb, "estado": estado}

    db.tabla("metricas").put_item(Item=util.a_dynamo({
        **metrica, "expiraEn": int(time.time()) + TTL_METRICAS_DIAS * 86400,
    }))

    antenas = db.tabla("antenas")
    for _ in range(INTENTOS):
        actual = antenas.get_item(Key={"antenaId": m["antenaId"]}, ConsistentRead=True).get("Item") or {}
        ultima = actual.get("actualizadoEn")
        if ultima and ultima >= medido_en:
            if ultima == medido_en and actual.get("cambioEn") == medido_en and actual.get("estado") == estado:
                # Reentrega de la métrica que provocó una transición: asegura que su evento de historial exista.
                _registrar_cambio(m["antenaId"], gb, estado, actual.get("estadoAnterior"), medido_en, simulada)
                return {**metrica, "ignorada": "reentrega: ya aplicada (historial verificado)"}
            return {**metrica, "ignorada": "lectura más vieja que el estado actual"}

        anterior = actual.get("estado")
        cambia = anterior != estado
        sets = ["zonaId = :z", "estado = :e", "gbPorMinuto = :gb", "actualizadoEn = :t", "estadoDesde = :d", "simulada = :sim"]
        valores = {":z": m["zonaId"], ":e": estado, ":gb": gb, ":t": medido_en, ":sim": simulada,
                   ":d": medido_en if cambia else (actual.get("estadoDesde") or medido_en)}
        if cambia:
            sets.append("cambioEn = :t")
            if anterior:
                sets.append("estadoAnterior = :ant")
                valores[":ant"] = anterior
        # Condición: nadie aplicó una lectura más nueva ni cambió el estado desde que lo leímos.
        condicion = "(attribute_not_exists(actualizadoEn) OR actualizadoEn < :t) AND " + (
            "estado = :ant0" if anterior else "attribute_not_exists(estado)")
        if anterior:
            valores[":ant0"] = anterior
        try:
            antenas.update_item(Key={"antenaId": m["antenaId"]}, UpdateExpression="SET " + ", ".join(sets),
                                ConditionExpression=condicion, ExpressionAttributeValues=util.a_dynamo(valores))
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                continue  # competimos con otra lectura: releer y decidir de nuevo
            raise
        if cambia:
            _registrar_cambio(m["antenaId"], gb, estado, anterior, medido_en, simulada)
        return metrica
    raise RuntimeError(f"Conflicto al actualizar la antena {m['antenaId']}: se reintentará")


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
