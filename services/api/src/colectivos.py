"""Incidentes colectivos (E3): consulta y acción del operador.

GET  /api/colectivos?todos=1          → abiertos (por defecto) o los de los últimos 7 días
GET  /api/colectivos/{id}             → detalle + historial + zona + incidencias (resumen)
POST /api/colectivos/{id}/restablecer → el operador marca el servicio como restablecido; la Step Function
                                        lo detecta en su próxima re-verificación y cierra el ciclo.
"""
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from telecorp import db, historial, http, reglas, util, zonas

_OCULTOS = {"taskToken"}


def _publico(c: dict) -> dict:
    zona = zonas.zona(c["zonaId"]) or {}
    salida = {k: v for k, v in c.items() if k not in _OCULTOS}
    salida["zona"] = {k: zona.get(k) for k in ("nombre", "tipo", "centro", "radioM", "clientesEstimados")}
    salida["afectados"] = len(c.get("usuariosAfectados", []))
    salida.pop("usuariosAfectados", None)  # datos personales: solo el conteo
    return salida


def listar(event, context):
    q = event.get("queryStringParameters") or {}
    items = db.scan_todo(db.tabla("colectivos"), FilterExpression=Attr("detectadoEn").gte(util.hace_iso(days=7)))
    if not q.get("todos"):
        items = [c for c in items if c["estado"] in reglas.ESTADOS_COLECTIVO_ABIERTOS or c["estado"] == "SERVICIO_RESTABLECIDO"]
    items.sort(key=lambda c: (c["estado"] == "CERRADO", -float(c.get("puntajePrioridad", 0)), c["detectadoEn"]))
    return http.ok({"colectivos": [_publico(c) for c in items]})


def obtener(event, context):
    cid = event["pathParameters"]["colectivoId"]
    c = db.tabla("colectivos").get_item(Key={"incidenteColectivoId": cid}).get("Item")
    if not c:
        return http.error(404, "Incidente colectivo no encontrado")
    eventos = db.tabla("historial").query(KeyConditionExpression=Key("entidadId").eq(cid))["Items"]
    t = db.tabla("incidencias")
    incidencias = []
    for iid in c.get("incidencias", [])[:50]:
        i = t.get_item(Key={"incidenciaId": iid}).get("Item")
        if i:
            incidencias.append({"incidenciaId": iid, "estado": i["estado"], "tipo": i["tipo"], "creadaEn": i["creadaEn"],
                                "descripcion": (i["reporte"].get("descripcion") or "")[:120]})
    return http.ok({"colectivo": _publico(c),
                    "historial": [{k: v for k, v in e.items() if k != "sk"} for e in eventos],
                    "incidencias": incidencias})


def restablecer(event, context):
    cid = event["pathParameters"]["colectivoId"]
    try:
        db.tabla("colectivos").update_item(
            Key={"incidenteColectivoId": cid},
            UpdateExpression="SET restablecimientoSolicitado = :v",
            ConditionExpression="estado IN (:e1, :e2)",
            ExpressionAttributeValues={":v": True, ":e1": "EN_EVALUACION", ":e2": "INCIDENCIA_CONFIRMADA"},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return http.error(409, "El incidente no está abierto")
        raise
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "COMENTARIO", "OPERADOR",
                        detalle="El operador marcó el servicio como restablecido")
    return http.ok({"incidenteColectivoId": cid, "restablecimientoSolicitado": True,
                    "mensaje": "La Step Function cerrará el incidente en su próxima verificación."})
