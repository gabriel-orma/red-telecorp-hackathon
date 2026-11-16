"""Cálculo del estado público de la red, estilo Downdetector (E3.5). Contrato: contracts/schemas/estado-red.schema.json

Vive en la layer porque lo usan dos funciones: el API (`GET /api/estado`) y el motor `detector`, que cada 5 min publica
una copia en Cloudflare (tercera nube, decisión D15) sin agregar Lambdas (D14).
"""
from datetime import timedelta

from boto3.dynamodb.conditions import Key

from telecorp import db, estadisticas as est, reglas, util, zonas

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


def _datos() -> dict:
    """Una sola pasada por las tablas: lo que necesitan el estado GLOBAL y el de cada zona."""
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
    return {"ahora": ahora, "buckets24": buckets24, "desde": desde, "colectivos": colectivos,
            "simulados": simulados_abiertos, "conColectivo": zonas_con_colectivo, "zonas": resumen_zonas}


def _armar(d: dict, alcance: str) -> dict:
    colectivos, resumen_zonas = d["colectivos"], d["zonas"]
    if alcance == "GLOBAL":
        principal = _resumen_serie(_serie("GLOBAL", d["desde"]), d["buckets24"])
        hay_problema = bool(colectivos)
    else:
        principal = next(z["_r"] for z in resumen_zonas if z["zonaId"] == alcance)
        hay_problema = alcance in d["conColectivo"]
    nivel = est.nivel(principal["ultimaHora"], principal["baseHora"], hay_problema)
    if alcance == "GLOBAL" and nivel == "SIN_PROBLEMAS" and any(z["nivel"] != "SIN_PROBLEMAS" for z in resumen_zonas):
        nivel = "POSIBLES_PROBLEMAS"  # algún pico local, aunque el total del país se vea normal

    total_tipos = sum(principal["tipos"].values()) or 1
    return {
        "generadoEn": util.iso(d["ahora"]), "alcance": alcance,
        "nivel": nivel, "mensaje": est.MENSAJES[nivel],
        "serie": principal["serie"],
        "totales": {"ultimas24h": principal["total24h"], "ultimaHora": principal["ultimaHora"], "baseHora": principal["baseHora"]},
        "tipos": sorted(({"tipo": tp, "total": n, "pct": round(100 * n / total_tipos, 1)} for tp, n in principal["tipos"].items() if n),
                        key=lambda x: -x["total"]),
        "zonas": [{k: v for k, v in z.items() if k != "_r"} for z in resumen_zonas],
        "colectivos": [c for c in colectivos if alcance == "GLOBAL" or c["zonaId"] == alcance],
        # Hay una simulación en curso: no cuenta en este panel (que muestra solo reportes y colectivos reales).
        "simulacion": {"colectivosAbiertos": d["simulados"]},
    }


def calcular(alcance: str) -> dict:
    """Estado público para GLOBAL o una zona (contrato estado-red)."""
    return _armar(_datos(), alcance)


def calcular_todo() -> dict:
    """{"GLOBAL": estado, "ZONA-01": estado, ...} con una sola lectura de las tablas (para el espejo de Cloudflare)."""
    d = _datos()
    return {"GLOBAL": _armar(d, "GLOBAL"), **{z["zonaId"]: _armar(d, z["zonaId"]) for z in d["zonas"]}}
