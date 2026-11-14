"""Incidencias de usuarios (E2).

POST  /api/reportes                    → valida, deduplica y encola en SQS (202). El worker la registra.
SQS   reportes → registrar             → put idempotente (condicional) + historial CREADO.
GET   /api/incidencias                 → lista (filtros: zonaId, estado, horas, limite).
GET   /api/incidencias/{id}            → detalle + historial + transiciones permitidas + estado de la zona.
PATCH /api/incidencias/{id}/estado     → cambio de estado validado + historial.

Los datos personales se devuelven enmascarados (no hay autenticación todavía).
"""
import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from telecorp import db, historial, http, notificador, reglas, util, zonas

_sqs = boto3.client("sqs")
VENTANA_DEDUP_HORAS = 24


# ---------------- Utilidades ----------------
def _publica(item: dict, completa: bool = False) -> dict:
    """Vista para el API: datos personales enmascarados."""
    rep = dict(item.get("reporte", {}))
    rep["usuarioId"] = reglas.enmascarar(rep.get("usuarioId"))
    rep["numeroServicio"] = reglas.enmascarar(rep.get("numeroServicio"))
    rep["email"] = reglas.enmascarar_email(rep.get("email"))
    rep["telefonoContacto"] = reglas.enmascarar(rep.get("telefonoContacto"), 4, 3)
    if not completa:
        rep["descripcion"] = (rep.get("descripcion") or "")[:160]
    salida = {**item, "reporte": rep, "usuarioId": rep["usuarioId"]}
    salida["transicionesPermitidas"] = reglas.transiciones_permitidas(item["estado"])
    return salida


def _incidencias_zona(zona_id: str, desde_iso: str) -> list:
    t, items, kwargs = db.tabla("incidencias"), [], {}
    while True:
        r = t.query(IndexName="zona-fecha",
                    KeyConditionExpression=Key("zonaId").eq(zona_id) & Key("creadaEn").gte(desde_iso),
                    ScanIndexForward=False, **kwargs)
        items.extend(r["Items"])
        if "LastEvaluatedKey" not in r:
            return items
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _historial(entidad_id: str) -> list:
    r = db.tabla("historial").query(KeyConditionExpression=Key("entidadId").eq(entidad_id))
    return [{k: v for k, v in e.items() if k != "sk"} for e in r["Items"]]


# ---------------- Endpoints ----------------
def crear_reporte(event, context):
    try:
        reporte = http.cuerpo_json(event)
    except ValueError as e:
        return http.error(400, str(e))
    reporte = {k: (v.strip() if isinstance(v, str) else v) for k, v in reporte.items()}

    errores = reglas.validar_reporte(reporte, {z["zonaId"] for z in zonas.zonas()})
    if errores:
        return http.error(400, "El reporte tiene errores", errores=errores)

    # Deduplicación atómica (clave condicional): un usuario con un reporte activo en la zona no genera otro,
    # así no cuenta dos veces para la regla de 10 usuarios. Es consistente aunque el worker aún no haya corrido.
    incidencia_id = util.nuevo_id("INC")
    clave = _clave_dedup(reporte["usuarioId"], reporte["zonaId"])
    ahora = int(time.time())
    try:
        db.tabla("dedup").put_item(
            Item={"clave": clave, "incidenciaId": incidencia_id, "expiraEn": ahora + VENTANA_DEDUP_HORAS * 3600},
            ConditionExpression="attribute_not_exists(clave) OR expiraEn < :ahora",
            ExpressionAttributeValues={":ahora": ahora},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        previa = db.tabla("dedup").get_item(Key={"clave": clave}, ConsistentRead=True).get("Item", {})
        return http.ok({"incidenciaId": previa.get("incidenciaId"), "duplicado": True,
                        "mensaje": "Ya tienes un reporte activo en esta zona; te mostramos su seguimiento."})

    # Avisos por correo (opt-in): SNS envía al usuario un correo para confirmar la suscripción.
    suscripcion = None
    if reporte.get("avisarPorEmail") and reporte.get("email"):
        try:
            suscripcion = "pendiente" if notificador.suscribir_email(reporte["email"], reporte["usuarioId"]) else None
        except Exception as e:  # noqa: BLE001 - el reporte no debe fallar por el canal de email
            print(f"No se pudo suscribir el email: {e!r}")

    mensaje = {"incidenciaId": incidencia_id, "creadaEn": util.ahora_iso(), "reporte": reporte}
    try:
        _sqs.send_message(QueueUrl=os.environ["COLA_REPORTES_URL"], MessageBody=json.dumps(mensaje))
    except Exception:
        db.tabla("dedup").delete_item(Key={"clave": clave})  # no bloquear al usuario si no se encoló
        raise
    return http.respuesta(202, {"incidenciaId": incidencia_id, "estado": "REGISTRADA", "duplicado": False,
                                "avisoEmail": suscripcion})


def _clave_dedup(usuario_id: str, zona_id: str) -> str:
    return f"{usuario_id}#{zona_id}"


def registrar(event, context):
    """Worker SQS: crea la incidencia de forma idempotente (los reintentos de SQS no duplican)."""
    fallidos = []
    for r in event.get("Records", []):
        try:
            m = json.loads(r["body"])
            rep = m["reporte"]
            item = {
                "incidenciaId": m["incidenciaId"], "estado": "REGISTRADA",
                "creadaEn": m["creadaEn"], "actualizadaEn": m["creadaEn"],
                "zonaId": rep["zonaId"], "usuarioId": rep["usuarioId"], "tipo": rep["tipo"],
                "reporte": rep,
            }
            try:
                db.tabla("incidencias").put_item(Item=util.a_dynamo(item),
                                                 ConditionExpression="attribute_not_exists(incidenciaId)")
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    continue  # ya registrada en un intento anterior
                raise
            historial.registrar(m["incidenciaId"], "INCIDENCIA", "CREADO", "USUARIO",
                                detalle=f"Zona {(zonas.zona(rep['zonaId']) or {}).get('nombre', rep['zonaId'])}",
                                estado_nuevo="REGISTRADA",
                                ocurrido_en=m["creadaEn"])
        except Exception as e:  # noqa: BLE001 - vuelve a la cola; tras 3 intentos, a la DLQ
            print(f"ERROR reporte {r.get('messageId')}: {e!r}")
            fallidos.append({"itemIdentifier": r["messageId"]})
    return {"batchItemFailures": fallidos}


def _liberar_dedup(item: dict) -> None:
    try:
        db.tabla("dedup").delete_item(
            Key={"clave": _clave_dedup(item["usuarioId"], item["zonaId"])},
            ConditionExpression="incidenciaId = :i", ExpressionAttributeValues={":i": item["incidenciaId"]},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def listar(event, context):
    q = event.get("queryStringParameters") or {}
    try:
        horas = min(max(int(q.get("horas", 72)), 1), 24 * 30)
        limite = min(max(int(q.get("limite", 200)), 1), 1000)
    except ValueError:
        return http.error(400, "horas y limite deben ser enteros")
    desde = util.hace_iso(hours=horas)
    if q.get("zonaId"):
        items = _incidencias_zona(q["zonaId"], desde)
    else:
        items = db.scan_todo(db.tabla("incidencias"), FilterExpression=Attr("creadaEn").gte(desde))
    if q.get("estado"):
        items = [i for i in items if i["estado"] == q["estado"]]
    items.sort(key=lambda i: i["creadaEn"], reverse=True)
    return http.ok({"incidencias": [_publica(i) for i in items[:limite]], "total": len(items)})


def obtener(event, context):
    incidencia_id = event["pathParameters"]["incidenciaId"]
    item = db.tabla("incidencias").get_item(Key={"incidenciaId": incidencia_id}).get("Item")
    if not item:
        return http.error(404, "Incidencia no encontrada (si la acabas de crear, se está registrando)")

    zona = zonas.zona(item["zonaId"]) or {}
    activas = [i for i in _incidencias_zona(item["zonaId"], util.hace_iso(hours=24))
               if i.get("estado") in reglas.ESTADOS_INCIDENCIA_ACTIVOS]
    antenas = db.tabla("antenas")
    estados_antenas = [antenas.get_item(Key={"antenaId": a["antenaId"]}).get("Item", {}).get("estado", "SIN_DATOS")
                       for a in zona.get("antenas", [])]
    colectivo = None
    if item.get("incidenteColectivoId"):
        c = db.tabla("colectivos").get_item(Key={"incidenteColectivoId": item["incidenteColectivoId"]}).get("Item")
        if c:
            colectivo = {k: c.get(k) for k in ("incidenteColectivoId", "estado", "pasoActual", "prioridad", "detectadoEn",
                                               "resueltoEn", "origen", "resumenIA")}
            colectivo["afectados"] = len(c.get("usuariosAfectados", []))
            colectivo["antenasEnFalla"] = len(c.get("antenasEnFalla", []))
    return http.ok({
        "colectivo": colectivo,
        "incidencia": _publica(item, completa=True),
        "historial": _historial(incidencia_id),
        "zona": {
            "zonaId": item["zonaId"], "nombre": zona.get("nombre"), "tipo": zona.get("tipo"),
            "estadoRed": reglas.peor_estado(estados_antenas),
            "antenasConFalla": sum(1 for e in estados_antenas if e in ("CAIDA", "INHABILITADA")),
            "reportesActivos24h": len(activas),
            "usuariosAfectados24h": len({i["usuarioId"] for i in activas}),
        },
    })


def cambiar_estado(event, context):
    incidencia_id = event["pathParameters"]["incidenciaId"]
    try:
        cuerpo = http.cuerpo_json(event)
    except ValueError as e:
        return http.error(400, str(e))
    nuevo = cuerpo.get("estado")
    comentario = str(cuerpo.get("comentario") or "")[:500]

    t = db.tabla("incidencias")
    item = t.get_item(Key={"incidenciaId": incidencia_id}).get("Item")
    if not item:
        return http.error(404, "Incidencia no encontrada")
    actual = item["estado"]
    if not reglas.transicion_valida(actual, nuevo):
        return http.error(409, f"No se puede pasar de {actual} a {nuevo}",
                          transicionesPermitidas=reglas.transiciones_permitidas(actual))

    ahora = util.ahora_iso()
    try:
        nuevo_item = t.update_item(
            Key={"incidenciaId": incidencia_id},
            UpdateExpression="SET estado = :n, actualizadaEn = :t",
            ConditionExpression="estado = :a",  # evita pisar un cambio concurrente
            ExpressionAttributeValues={":n": nuevo, ":t": ahora, ":a": actual},
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return http.error(409, "La incidencia cambió mientras tanto; recarga e inténtalo de nuevo")
        raise
    historial.registrar(incidencia_id, "INCIDENCIA", "CAMBIO_ESTADO", "OPERADOR",
                        detalle=comentario, estado_anterior=actual, estado_nuevo=nuevo, ocurrido_en=ahora)
    if nuevo not in reglas.ESTADOS_INCIDENCIA_ACTIVOS:
        _liberar_dedup(item)  # resuelta: el usuario ya puede volver a reportar en esa zona
    return http.ok({"incidencia": _publica(nuevo_item, completa=True)})
