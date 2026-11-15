"""Estado público de la red, estilo Downdetector (E3.5). Contrato: contracts/schemas/estado-red.schema.json

GET /api/estado?zonaId=ZONA-05   (sin zonaId → GLOBAL)
GET /api/config                  → ids públicos de Cognito para el frontend
"""
import os
import time
from datetime import timedelta

from boto3.dynamodb.conditions import Key

from telecorp import db, estadisticas as est, http, reglas, util, zonas

_cache: dict = {}
CACHE_SEGUNDOS = 10
TIPOS = sorted(reglas.TIPOS_PROBLEMA)


def _serie(nombre: str, desde: str) -> dict:
    """{bucket: item} de una serie desde `desde`."""
    t, items, kwargs = db.tabla("estadisticas"), {}, {}
    while True:
        r = t.query(KeyConditionExpression=Key("serie").eq(nombre) & Key("bucket").gte(desde), **kwargs)
        for i in r["Items"]:
            items[i["bucket"]] = i
        if "LastEvaluatedKey" not in r:
            return items
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _resumen_serie(items: dict, buckets24: list) -> dict:
    conteos = {b: int(i.get("total", 0)) for b, i in items.items()}
    serie = [{"t": b, "total": conteos.get(b, 0), "base": est.linea_base(conteos, b)} for b in buckets24]
    ultima_hora = sum(p["total"] for p in serie[-4:])
    base_hora = round(sum(p["base"] for p in serie[-4:]), 2)
    tipos = {tp: sum(int(items.get(b, {}).get(f"t_{tp}", 0)) for b in buckets24) for tp in TIPOS}
    return {"serie": serie, "ultimaHora": ultima_hora, "baseHora": base_hora,
            "total24h": sum(p["total"] for p in serie), "tipos": tipos}


def _colectivos_activos() -> tuple:
    """(operativos abiertos, cuántos colectivos SIMULADOS hay abiertos). Los simulados no mueven el semáforo público."""
    from boto3.dynamodb.conditions import Attr
    todos = db.scan_todo(db.tabla("colectivos"),
                         FilterExpression=Attr("estado").is_in(list(reglas.ESTADOS_COLECTIVO_ABIERTOS | {"REQUIERE_ATENCION"})))
    items = [c for c in todos if not reglas.es_simulado(c)]
    return [{"incidenteColectivoId": c["incidenteColectivoId"], "zonaId": c["zonaId"],
             "nombre": (zonas.zona(c["zonaId"]) or {}).get("nombre"), "estado": c["estado"],
             "prioridad": c.get("prioridad"), "afectados": len(c.get("usuariosAfectados", [])),
             "detectadoEn": c["detectadoEn"], "antenasEnFalla": len(c.get("antenasEnFalla", []))} for c in items], len(todos) - len(items)


def _calcular(alcance: str) -> dict:
    ahora = util.ahora()
    buckets24 = est.buckets_ultimas_24h(ahora)
    desde = est.bucket(ahora - timedelta(days=est.DIAS_BASE + 1))
    colectivos, simulados_abiertos = _colectivos_activos()
    zonas_con_colectivo = {c["zonaId"] for c in colectivos}

    # Resumen por zona (ranking + semáforo por zona)
    resumen_zonas = []
    for z in zonas.zonas():
        r = _resumen_serie(_serie(z["zonaId"], desde), buckets24)
        resumen_zonas.append({
            "zonaId": z["zonaId"], "nombre": z["nombre"], "tipo": z["tipo"], "centro": z["centro"], "radioM": z["radioM"],
            "total24h": r["total24h"], "ultimaHora": r["ultimaHora"], "baseHora": r["baseHora"],
            "nivel": est.nivel(r["ultimaHora"], r["baseHora"], z["zonaId"] in zonas_con_colectivo),
            "_r": r,
        })
    resumen_zonas.sort(key=lambda z: (-z["total24h"], z["nombre"]))

    if alcance == "GLOBAL":
        principal = _resumen_serie(_serie("GLOBAL", desde), buckets24)
        hay_problema = bool(colectivos)
    else:
        principal = next(z["_r"] for z in resumen_zonas if z["zonaId"] == alcance)
        hay_problema = alcance in zonas_con_colectivo
    nivel = est.nivel(principal["ultimaHora"], principal["baseHora"], hay_problema)
    if alcance == "GLOBAL" and nivel == "SIN_PROBLEMAS" and any(z["nivel"] != "SIN_PROBLEMAS" for z in resumen_zonas):
        nivel = "POSIBLES_PROBLEMAS"  # algún pico local, aunque el total del país se vea normal

    total_tipos = sum(principal["tipos"].values()) or 1
    return {
        "generadoEn": util.iso(ahora), "alcance": alcance,
        "nivel": nivel, "mensaje": est.MENSAJES[nivel],
        "serie": principal["serie"],
        "totales": {"ultimas24h": principal["total24h"], "ultimaHora": principal["ultimaHora"], "baseHora": principal["baseHora"]},
        "tipos": sorted(({"tipo": tp, "total": n, "pct": round(100 * n / total_tipos, 1)} for tp, n in principal["tipos"].items() if n),
                        key=lambda x: -x["total"]),
        "zonas": [{k: v for k, v in z.items() if k != "_r"} for z in resumen_zonas],
        "colectivos": [c for c in colectivos if alcance == "GLOBAL" or c["zonaId"] == alcance],
        # Hay una simulación en curso: no cuenta en este panel (que muestra solo reportes y colectivos reales).
        "simulacion": {"colectivosAbiertos": simulados_abiertos},
    }


def estado(event, context):
    alcance = (event.get("queryStringParameters") or {}).get("zonaId") or "GLOBAL"
    if alcance != "GLOBAL" and not zonas.zona(alcance):
        return http.error(404, f"Zona desconocida: {alcance}")
    ahora = time.time()
    if alcance not in _cache or ahora - _cache[alcance][0] > CACHE_SEGUNDOS:
        _cache[alcance] = (ahora, _calcular(alcance))
    respuesta = http.ok(_cache[alcance][1])
    respuesta["headers"]["cache-control"] = f"public, max-age={CACHE_SEGUNDOS}"
    return respuesta


def config(event, context):
    return http.ok({"region": os.environ.get("AWS_REGION", "us-east-1"),
                    "userPoolId": os.environ["USER_POOL_ID"], "clientId": os.environ["USER_POOL_CLIENT_ID"],
                    "wsUrl": os.environ.get("WS_URL")})
