"""Operaciones sobre incidentes colectivos compartidas por el detector y los pasos de la Step Function."""
import json
import os
import time

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from telecorp import db, escenarios, historial, notificador, reglas, util, zonas

_sfn = boto3.client("stepfunctions")
LOCK_DIAS = 7


# ---------------- Lectura ----------------
def obtener(colectivo_id: str) -> dict:
    item = db.tabla("colectivos").get_item(Key={"incidenteColectivoId": colectivo_id}, ConsistentRead=True).get("Item")
    if not item:
        raise ValueError(f"Colectivo no encontrado: {colectivo_id}")
    return item


def incidencias_activas_zona(zona_id: str, horas: int) -> list:
    t, items, kwargs = db.tabla("incidencias"), [], {}
    while True:
        r = t.query(IndexName="zona-fecha",
                    KeyConditionExpression=Key("zonaId").eq(zona_id) & Key("creadaEn").gte(util.hace_iso(hours=horas)),
                    **kwargs)
        items.extend(i for i in r["Items"] if i.get("estado") in reglas.ESTADOS_INCIDENCIA_ACTIVOS)
        if "LastEvaluatedKey" not in r:
            return items
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def estados_antenas_zona(zona_id: str) -> dict:
    t = db.tabla("antenas")
    return {a["antenaId"]: t.get_item(Key={"antenaId": a["antenaId"]}).get("Item", {}).get("estado", "SIN_DATOS")
            for a in (zonas.zona(zona_id) or {}).get("antenas", [])}


# ---------------- Candado: un solo colectivo abierto por zona ----------------
def _clave_lock(zona_id: str) -> str:
    return f"COLECTIVO#{zona_id}"


def colectivo_abierto(zona_id: str) -> str | None:
    item = db.tabla("dedup").get_item(Key={"clave": _clave_lock(zona_id)}, ConsistentRead=True).get("Item")
    if item and int(item.get("expiraEn", 0)) > time.time():
        return item["incidenciaId"]  # la tabla dedup guarda el id en el atributo incidenciaId
    return None


def tomar_lock(zona_id: str, colectivo_id: str) -> str | None:
    """Reserva la zona para este colectivo. Si ya hay otro abierto, devuelve su id (y no reserva)."""
    ahora = int(time.time())
    try:
        db.tabla("dedup").put_item(
            Item={"clave": _clave_lock(zona_id), "incidenciaId": colectivo_id, "expiraEn": ahora + LOCK_DIAS * 86400},
            ConditionExpression="attribute_not_exists(clave) OR expiraEn < :ahora",
            ExpressionAttributeValues={":ahora": ahora},
        )
        return None
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return colectivo_abierto(zona_id)


def liberar_lock(zona_id: str, colectivo_id: str) -> None:
    try:
        db.tabla("dedup").delete_item(Key={"clave": _clave_lock(zona_id)}, ConditionExpression="incidenciaId = :c",
                                      ExpressionAttributeValues={":c": colectivo_id})
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def liberar_dedup_usuario(incidencia: dict) -> None:
    try:
        db.tabla("dedup").delete_item(Key={"clave": f"{incidencia['usuarioId']}#{incidencia['zonaId']}"},
                                      ConditionExpression="incidenciaId = :i",
                                      ExpressionAttributeValues={":i": incidencia["incidenciaId"]})
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


# ---------------- Escritura ----------------
def actualizar(colectivo_id: str, **campos) -> None:
    nombres = {f"#{k}": k for k in campos}
    valores = {f":{k}": v for k, v in campos.items()}
    db.tabla("colectivos").update_item(
        Key={"incidenteColectivoId": colectivo_id},
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in campos),
        ExpressionAttributeNames=nombres, ExpressionAttributeValues=util.a_dynamo(valores),
    )


def marcar_paso(colectivo_id: str, paso: str) -> None:
    actualizar(colectivo_id, pasoActual=paso, actualizadoEn=util.ahora_iso())


def agrupar_incidencias(col: dict, incidencias: list, notificar_estado: bool) -> int:
    """Suma incidencias (y sus usuarios) al colectivo. Devuelve cuántas eran nuevas."""
    ya = set(col.get("incidencias", []))
    nuevas = [i for i in incidencias if i["incidenciaId"] not in ya]
    if not nuevas:
        return 0
    usuarios = sorted(set(col.get("usuariosAfectados", [])) | {i["usuarioId"] for i in nuevas})
    lista = list(col.get("incidencias", [])) + [i["incidenciaId"] for i in nuevas]
    cambios = {"incidencias": lista, "usuariosAfectados": usuarios}
    primeras = min(i["creadaEn"] for i in nuevas)
    if not col.get("primerReporteEn") or primeras < col["primerReporteEn"]:
        cambios["primerReporteEn"] = primeras
    if col.get("origen") == "METRICAS_ANTENA":
        cambios["origen"] = "AMBOS"
    actualizar(col["incidenteColectivoId"], **cambios)
    col.update(cambios)
    for i in nuevas:
        db.tabla("incidencias").update_item(
            Key={"incidenciaId": i["incidenciaId"]}, UpdateExpression="SET incidenteColectivoId = :c",
            ExpressionAttributeValues={":c": col["incidenteColectivoId"]})
        historial.registrar(i["incidenciaId"], "INCIDENCIA", "AGRUPADO", "SISTEMA",
                            detalle=f"Agrupada en el incidente colectivo {col['incidenteColectivoId']}")
        # Quien se suma a un colectivo ya en marcha recibe de inmediato el aviso del estado actual.
        if notificar_estado and col.get("estado") in notificador.MENSAJES:
            notificador.notificar(i, col["estado"], col["incidenteColectivoId"])
    return len(nuevas)


def agregar_antenas(col: dict, antenas: list) -> None:
    actuales = {a["antenaId"]: a for a in col.get("antenasEnFalla", [])}
    nuevas = [a for a in antenas if a["antenaId"] not in actuales]
    if not nuevas:
        return
    cambios = {"antenasEnFalla": list(actuales.values()) + nuevas}
    if col.get("usuariosAfectados") and col.get("origen") == "REPORTES_USUARIOS":
        cambios["origen"] = "AMBOS"
    falla_en = min(a.get("desde") or util.ahora_iso() for a in nuevas)
    if not col.get("primeraFallaEn") or falla_en < col["primeraFallaEn"]:
        cambios["primeraFallaEn"] = falla_en
    actualizar(col["incidenteColectivoId"], **cambios)
    col.update(cambios)
    for a in nuevas:
        historial.registrar(col["incidenteColectivoId"], "INCIDENTE_COLECTIVO", "COMENTARIO", "SISTEMA",
                            detalle=f"Antena {a['antenaId']} en estado {a['estado']}")


def crear(zona_id: str, origen: str, detalle: str, incidencias: list, antenas: list) -> str:
    """Crea el colectivo (o se suma al que ya esté abierto en la zona) y arranca la Step Function."""
    colectivo_id = util.nuevo_id("COL")
    existente = tomar_lock(zona_id, colectivo_id)
    if existente:
        col = obtener(existente)
        agrupar_incidencias(col, incidencias, notificar_estado=True)
        agregar_antenas(col, antenas)
        return existente

    ahora = util.ahora_iso()
    acelerada = _simulacion_acelerada()
    col = {
        "incidenteColectivoId": colectivo_id, "zonaId": zona_id, "origen": origen, "origenDetalle": detalle,
        "detectadoEn": ahora, "actualizadoEn": ahora, "resueltoEn": None,
        "estado": "EN_EVALUACION", "pasoActual": "DETECTADO",
        "usuariosAfectados": [], "incidencias": [], "antenasEnFalla": [],
        "primerReporteEn": None, "primeraFallaEn": None,
        "prioridad": "BAJA", "puntajePrioridad": 0, "notificacionesEnviadas": 0,
        "restablecimientoSolicitado": False,
        # Simulación acelerada: el tiempo activo cuenta x60 para la prioridad (escala en segundos, no en horas).
        **({"factorTiempo": escenarios.FACTOR_TIEMPO_ACELERADA} if acelerada else {}),
    }
    db.tabla("colectivos").put_item(Item=util.a_dynamo(col))
    historial.registrar(colectivo_id, "INCIDENTE_COLECTIVO", "CREADO", "SISTEMA", detalle=detalle,
                        estado_nuevo="EN_EVALUACION")
    agrupar_incidencias(col, incidencias, notificar_estado=False)  # la SFN notifica a todos en su primer paso
    agregar_antenas(col, antenas)

    cfg = _reglas_colectivo()
    espera = int(cfg.get("esperaVerificacionSegundos", 30))
    if acelerada:
        espera = min(espera, ESPERA_ACELERADA_S)
    ejecucion = _sfn.start_execution(
        stateMachineArn=os.environ["MAQUINA_COLECTIVO"], name=colectivo_id,
        input=json.dumps({"colectivoId": colectivo_id, "esperaSegundos": espera,
                          "monitoreo": {"iteracion": 0}}),
    )
    actualizar(colectivo_id, ejecucionArn=ejecucion["executionArn"])
    return colectivo_id


ESPERA_ACELERADA_S = 4  # monitoreo cada 4 s durante la simulación acelerada (normal: 30 s)


def _simulacion_acelerada() -> bool:
    from telecorp import config
    try:
        e = config.leer("escenario", usar_cache=False)
    except Exception:  # noqa: BLE001 - sin el parámetro, flujo normal
        return False
    return bool(e.get("activo") and e.get("tipo") == "ACELERADA")


def _reglas_colectivo() -> dict:
    from telecorp import config
    return config.leer("reglas").get("colectivo", {})
