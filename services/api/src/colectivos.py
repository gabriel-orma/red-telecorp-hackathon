"""Incidentes colectivos (E3): consulta y acción del operador.

GET  /api/colectivos?todos=1          → abiertos (por defecto) o los de los últimos 7 días (público: solo conteos)
GET  /api/colectivos/{id}             → detalle + historial + zona + incidencias (resumen). Solo operadores.
POST /api/colectivos/{id}/restablecer → el operador marca el servicio como restablecido; la Step Function
                                        lo detecta en su próxima re-verificación y cierra el ciclo. Solo operadores.
                                        Si el incidente estaba en REQUIERE_ATENCION (el flujo automático se detuvo), lo retoma:
                                        vuelve a reservar la zona y arranca una ejecución que lo cierra con el flujo normal
                                        (avisos de «restablecido», incidencias solucionadas, historial). 409 si la zona ya
                                        tiene otro incidente abierto.

"Solo operadores" = autorizador JWT en la ruta + grupo `operadores` comprobado en el handler (ver `acceso.py`).
"""
import json
import os
import sys as _sys
import time

import boto3

_sys.path.insert(0, os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from telecorp import db, historial, http, reglas, util, zonas
import acceso  # noqa: E402

_sfn = boto3.client("stepfunctions")

_OCULTOS = {"taskToken"}
LOCK_DIAS = 7


def _publico(c: dict) -> dict:
    zona = zonas.zona(c["zonaId"]) or {}
    salida = {k: v for k, v in c.items() if k not in _OCULTOS}
    salida["zona"] = {k: zona.get(k) for k in ("nombre", "tipo", "centro", "radioM", "clientesEstimados")}
    salida["afectados"] = len(c.get("usuariosAfectados", []))
    salida["deteccionAnticipadaMin"] = reglas.deteccion_anticipada_min(c.get("primeraFallaEn"), c.get("primerReporteEn"))
    salida.pop("usuariosAfectados", None)  # datos personales: solo el conteo
    return salida


def listar(event, context):
    q = event.get("queryStringParameters") or {}
    items = db.scan_todo(db.tabla("colectivos"), FilterExpression=Attr("detectadoEn").gte(util.hace_iso(days=7)))
    if not q.get("todos"):
        visibles = reglas.ESTADOS_COLECTIVO_ABIERTOS | {"SERVICIO_RESTABLECIDO", "REQUIERE_ATENCION"}   # atención manual: el operador debe verlo
        items = [c for c in items if c["estado"] in visibles]
    items.sort(key=lambda c: (c["estado"] == "CERRADO", -float(c.get("puntajePrioridad", 0)), c["detectadoEn"]))
    return http.ok({"colectivos": [_publico(c) for c in items]})


@acceso.solo_operadores
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


def _clave_candado(zona_id: str, simulado: bool) -> str:
    """Misma clave que `comun_colectivos._clave_lock` (workflows): la prueba `test_la_clave_del_candado_coincide` las vigila."""
    return f"LOCK#COLECTIVO#{zona_id}{'~SIM' if simulado else ''}"


def _reservar_zona(clave: str, cid: str) -> str | None:
    """Vuelve a tomar el candado de la zona para `cid`. None si lo logró; si no, el id del OTRO colectivo que la ocupa.
    Un candado cuyo dueño ya no está abierto (huérfano) se libera y se reintenta."""
    t = db.tabla("dedup")
    for _ in range(2):
        try:
            t.put_item(Item={"clave": clave, "incidenciaId": cid, "expiraEn": int(time.time()) + LOCK_DIAS * 86400},
                       ConditionExpression="attribute_not_exists(clave) OR expiraEn < :ahora OR incidenciaId = :c",
                       ExpressionAttributeValues={":ahora": int(time.time()), ":c": cid})
            return None
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
        dueno = (t.get_item(Key={"clave": clave}, ConsistentRead=True).get("Item") or {}).get("incidenciaId")
        otro = db.tabla("colectivos").get_item(Key={"incidenteColectivoId": dueno}, ConsistentRead=True).get("Item") if dueno else None
        if otro and otro.get("estado") in reglas.ESTADOS_COLECTIVO_ABIERTOS:
            return dueno
        try:  # huérfano: su colectivo no existe o ya no está abierto
            t.delete_item(Key={"clave": clave}, ConditionExpression="incidenciaId = :d", ExpressionAttributeValues={":d": dueno})
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
    return dueno or "desconocido"


def _liberar_zona(clave: str, cid: str) -> None:
    try:
        db.tabla("dedup").delete_item(Key={"clave": clave}, ConditionExpression="incidenciaId = :c",
                                      ExpressionAttributeValues={":c": cid})
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def _retomar_atencion_manual(event, cid: str):
    """REQUIERE_ATENCION → el operador confirma que el servicio volvió: se reserva la zona, el colectivo vuelve a su estado
    anterior con el restablecimiento solicitado y una ejecución nueva (modo `reanudar`) lo cierra con el flujo normal.
    Cada paso es reversible: si algo falla, el colectivo queda como estaba (REQUIERE_ATENCION) y la zona libre."""
    t = db.tabla("colectivos")
    col = t.get_item(Key={"incidenteColectivoId": cid}, ConsistentRead=True).get("Item")
    if not col or col.get("estado") != "REQUIERE_ATENCION":
        return http.error(409, "El incidente no está abierto")
    clave = _clave_candado(col["zonaId"], reglas.es_simulado(col))
    ocupante = _reservar_zona(clave, cid)
    if ocupante:
        return http.error(409, f"La zona ya tiene otro incidente colectivo abierto ({ocupante}): ciérralo antes de retomar este")
    previo = col.get("estadoAntesDeAtencion") if col.get("estadoAntesDeAtencion") in reglas.ESTADOS_COLECTIVO_ABIERTOS else "EN_EVALUACION"
    ahora = util.ahora_iso()
    try:
        t.update_item(Key={"incidenteColectivoId": cid},
                      UpdateExpression="SET estado = :p, pasoActual = :s, actualizadoEn = :t, restablecimientoSolicitado = :v REMOVE ejecucionArn",
                      ConditionExpression="estado = :ra",
                      ExpressionAttributeValues={":p": previo, ":s": "MONITOREAR", ":t": ahora, ":v": True, ":ra": "REQUIERE_ATENCION"})
    except ClientError as e:
        _liberar_zona(clave, cid)
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return http.error(409, "El incidente ya no requiere atención (otro operador lo retomó)")
        raise
    try:
        ejecucion = _sfn.start_execution(
            stateMachineArn=os.environ["MAQUINA_COLECTIVO"], name=f"{cid}-a{int(time.time())}",
            input=json.dumps({"colectivoId": cid, "reanudar": True, "esperaSegundos": 10, "monitoreo": {"iteracion": 0},
                              "prioridad": {"afectados": len(col.get("usuariosAfectados", []))}}))["executionArn"]
    except Exception:  # noqa: BLE001 - se deshace todo: el operador puede reintentar
        t.update_item(Key={"incidenteColectivoId": cid},
                      UpdateExpression="SET estado = :ra, pasoActual = :s, restablecimientoSolicitado = :f",
                      ExpressionAttributeValues={":ra": "REQUIERE_ATENCION", ":s": "ATENCION_MANUAL", ":f": False})
        _liberar_zona(clave, cid)
        return http.error(502, "No se pudo arrancar el cierre automático; el incidente sigue en atención manual. Reintenta.")
    t.update_item(Key={"incidenteColectivoId": cid}, UpdateExpression="SET ejecucionArn = :a",
                  ExpressionAttributeValues={":a": ejecucion})
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "CAMBIO_ESTADO", f"operador:{acceso.identidad(event)}",
                        detalle="El operador retomó el incidente y confirmó el servicio restablecido",
                        estado_anterior="REQUIERE_ATENCION", estado_nuevo=previo)
    return http.ok({"incidenteColectivoId": cid, "restablecimientoSolicitado": True, "retomado": True,
                    "mensaje": "Se retomó el incidente: el flujo avisará a los afectados y lo cerrará en unos segundos."})


@acceso.solo_operadores
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
            return _retomar_atencion_manual(event, cid)   # 409 si tampoco estaba en atención manual
        raise
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "COMENTARIO", f"operador:{acceso.identidad(event)}",
                        detalle="El operador marcó el servicio como restablecido")
    return http.ok({"incidenteColectivoId": cid, "restablecimientoSolicitado": True,
                    "mensaje": "La Step Function cerrará el incidente en su próxima verificación."})


def reanudar_huerfanos() -> list:
    """Incidentes abiertos cuya Step Function ya no corre (falló o se detuvo, p. ej. al apagarse el Learner Lab):
    arranca una ejecución nueva en modo `reanudar`, que entra directo al monitoreo. Devuelve los ids reanudados."""
    abiertos = db.scan_todo(db.tabla("colectivos"), FilterExpression=Attr("estado").is_in(list(reglas.ESTADOS_COLECTIVO_ABIERTOS)))
    reanudados = []
    for c in abiertos:
        arn = c.get("ejecucionArn")
        try:
            if arn and _sfn.describe_execution(executionArn=arn)["status"] == "RUNNING":
                continue
        except _sfn.exceptions.ExecutionDoesNotExist:
            pass
        cid = c["incidenteColectivoId"]
        nueva = _sfn.start_execution(
            stateMachineArn=os.environ["MAQUINA_COLECTIVO"], name=f"{cid}-r{int(time.time())}",
            input=json.dumps({"colectivoId": cid, "reanudar": True, "esperaSegundos": 10, "monitoreo": {"iteracion": 0},
                              "prioridad": {"afectados": len(c.get("usuariosAfectados", []))}}))
        db.tabla("colectivos").update_item(Key={"incidenteColectivoId": cid}, UpdateExpression="SET ejecucionArn = :a",
                                           ExpressionAttributeValues={":a": nueva["executionArn"]})
        historial.registrar(cid, "INCIDENTE_COLECTIVO", "COMENTARIO", "SISTEMA",
                            detalle="Monitoreo reanudado (la ejecución anterior se había detenido)")
        reanudados.append(cid)
    return reanudados


@acceso.solo_operadores
def reanudar(event, context):
    """POST /api/colectivos/reanudar → reanuda los incidentes huérfanos (ver reanudar_huerfanos)."""
    return http.ok({"reanudados": reanudar_huerfanos()})
