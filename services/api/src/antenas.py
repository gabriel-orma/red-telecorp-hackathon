"""Lectura del estado de la red: antenas, zonas y serie de métricas."""
from boto3.dynamodb.conditions import Key

from telecorp import db, http, reglas, util, zonas


def _estados_actuales() -> dict:
    return {a["antenaId"]: a for a in db.scan_todo(db.tabla("antenas"))}


def listar_antenas(event, context):
    """GET /api/antenas → catálogo + estado actual (SIN_DATOS si nunca reportó)."""
    actuales = _estados_actuales()
    salida = []
    for a in zonas.antenas():
        act = actuales.get(a["antenaId"], {})
        salida.append({
            **a,
            "estado": act.get("estado", "SIN_DATOS"),
            "gbPorMinuto": act.get("gbPorMinuto"),
            "actualizadoEn": act.get("actualizadoEn"),
            "estadoDesde": act.get("estadoDesde"),
        })
    return http.ok({"antenas": salida, "generadoEn": util.ahora_iso()})


def listar_zonas(event, context):
    """GET /api/zonas → catálogo + resumen por zona (peor estado y conteos por estado)."""
    actuales = _estados_actuales()
    tipos = zonas.catalogo()["tiposZona"]
    salida = []
    for z in zonas.zonas():
        estados = [actuales.get(a["antenaId"], {}).get("estado", "SIN_DATOS") for a in z["antenas"]]
        trafico = sum(float(actuales.get(a["antenaId"], {}).get("gbPorMinuto", 0) or 0) for a in z["antenas"])
        salida.append({
            **z,
            "criticidad": tipos.get(z["tipo"], 1),
            "estado": reglas.peor_estado(estados),
            "conteo": {e: estados.count(e) for e in set(estados)},
            "traficoGbPorMinuto": round(trafico, 1),
        })
    return http.ok({"zonas": salida, "tiposZona": tipos, "generadoEn": util.ahora_iso()})


def metricas_antena(event, context):
    """GET /api/antenas/{antenaId}/metricas?minutos=30 → serie para el gráfico del popup."""
    antena_id = event["pathParameters"]["antenaId"]
    if not zonas.zona_de_antena(antena_id):
        return http.error(404, f"Antena desconocida: {antena_id}")
    try:
        minutos = min(max(int((event.get("queryStringParameters") or {}).get("minutos", 30)), 1), 1440)
    except ValueError:
        return http.error(400, "minutos debe ser un entero")
    resp = db.tabla("metricas").query(
        KeyConditionExpression=Key("antenaId").eq(antena_id) & Key("medidoEn").gte(util.hace_iso(minutes=minutos)),
        ProjectionExpression="medidoEn, gbPorMinuto, estado",
    )
    return http.ok({"antenaId": antena_id, "metricas": resp["Items"]})
