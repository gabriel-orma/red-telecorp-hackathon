"""Analítica operativa (E6). Contrato: contracts/schemas/analitica.schema.json

GET  /api/analitica?dias=7   → KPIs, zonas, antenas más problemáticas, tipos, incidentes (duración y afectados)
POST /api/recurrencia        → ejecuta ahora la Step Function de recurrencia (además de la ejecución diaria)
"""
import json
import os
import statistics
import time

import boto3
from boto3.dynamodb.conditions import Attr, Key

from telecorp import config, db, estadisticas as est, http, reglas, util, zonas

_sfn = boto3.client("stepfunctions")
_cache: dict = {}
CACHE_SEGUNDOS = 60


def _suma_serie(serie: str, desde: str) -> dict:
    """Suma total y por tipo de una serie de estadísticas desde `desde`."""
    t, totales, kwargs = db.tabla("estadisticas"), {"total": 0}, {}
    while True:
        r = t.query(KeyConditionExpression=Key("serie").eq(serie) & Key("bucket").gte(desde), **kwargs)
        for item in r["Items"]:
            for k, v in item.items():
                if k == "total" or k.startswith("t_"):
                    totales[k] = totales.get(k, 0) + int(v)
        if "LastEvaluatedKey" not in r:
            return totales
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _calcular(dias: int) -> dict:
    desde = util.hace_iso(days=dias)
    desde_bucket = est.bucket(util.ahora()) if dias == 0 else est.bucket_de_iso(desde)

    # Incidentes colectivos del periodo
    cols = db.scan_todo(db.tabla("colectivos"), FilterExpression=Attr("detectadoEn").gte(desde))
    incidentes = []
    for c in cols:
        abierto = c["estado"] in reglas.ESTADOS_COLECTIVO_ABIERTOS
        duracion = (float(c["duracionMinutos"]) if c.get("duracionMinutos") is not None
                    else round((util.ahora() - util.parse_iso(c["detectadoEn"])).total_seconds() / 60, 1) if abierto else None)
        incidentes.append({
            "incidenteColectivoId": c["incidenteColectivoId"], "zonaId": c["zonaId"],
            "nombre": (zonas.zona(c["zonaId"]) or {}).get("nombre"), "detectadoEn": c["detectadoEn"],
            "estado": c["estado"], "abierto": abierto, "duracionMin": duracion,
            "afectados": len(c.get("usuariosAfectados", [])), "prioridad": c.get("prioridad"),
            "puntaje": float(c.get("puntajePrioridad", 0)), "origen": c.get("origen"),
            "deteccionAnticipadaMin": reglas.deteccion_anticipada_min(c.get("primeraFallaEn"), c.get("primerReporteEn")),
        })
    incidentes.sort(key=lambda i: i["detectadoEn"])

    # Reportes y tipos (contadores agregados, D10)
    glob = _suma_serie("GLOBAL", desde_bucket)
    total_tipos = sum(v for k, v in glob.items() if k.startswith("t_")) or 1
    tipos = sorted(({"tipo": k[2:], "total": v, "pct": round(100 * v / total_tipos, 1)} for k, v in glob.items() if k.startswith("t_")),
                   key=lambda x: -x["total"])

    # Zonas
    zonas_out = []
    for z in zonas.zonas():
        de_zona = [i for i in incidentes if i["zonaId"] == z["zonaId"]]
        zonas_out.append({"zonaId": z["zonaId"], "nombre": z["nombre"], "tipo": z["tipo"], "incidentes": len(de_zona),
                          "reportes": _suma_serie(z["zonaId"], desde_bucket)["total"],
                          "afectados": sum(i["afectados"] for i in de_zona)})
    zonas_out.sort(key=lambda z: (-z["incidentes"], -z["reportes"]))

    # Antenas más problemáticas (entradas en falla según el historial)
    hist, tabla_antenas = db.tabla("historial"), db.tabla("antenas")
    antenas_out = []
    for a in zonas.antenas():
        eventos = hist.query(KeyConditionExpression=Key("entidadId").eq(a["antenaId"]) & Key("sk").gte(desde))["Items"]
        fallas = reglas.contar_fallas(eventos, desde)
        estructural = tabla_antenas.get_item(Key={"antenaId": a["antenaId"]}).get("Item", {}).get("estructural")
        if fallas or estructural:
            antenas_out.append({"antenaId": a["antenaId"], "zonaId": a["zonaId"],
                                "zona": (zonas.zona(a["zonaId"]) or {}).get("nombre"), "fallas": fallas,
                                "estructural": bool(estructural)})
    antenas_out.sort(key=lambda a: (-a["fallas"], a["antenaId"]))

    anticipadas = [i["deteccionAnticipadaMin"] for i in incidentes if i["deteccionAnticipadaMin"] is not None]
    cerrados = [i["duracionMin"] for i in incidentes if not i["abierto"] and i["duracionMin"] is not None]
    rec_cfg = {"umbralFallas": 3, "ventanaDias": 7, **config.leer("reglas").get("recurrencia", {})}
    return {
        "dias": dias, "generadoEn": util.ahora_iso(),
        "kpis": {
            "incidentes": len(incidentes),
            "abiertos": sum(1 for i in incidentes if i["abierto"]),
            "duracionPromedioMin": round(sum(cerrados) / len(cerrados), 1) if cerrados else None,
            "afectadosTotales": sum(i["afectados"] for i in incidentes),
            # Mediana (no promedio): un incidente atípico (p. ej. uno que quedó abierto horas) no la distorsiona.
            "deteccionAnticipadaPromedioMin": round(statistics.median(anticipadas), 1) if anticipadas else None,
            # La red lo vio primero: falla antes del primer reporte, o detección proactiva sin reportes.
            "detectadosPrimeroPorLaRed": sum(1 for i in incidentes if (i["deteccionAnticipadaMin"] or 0) > 0
                                             or (i["origen"] == "METRICAS_ANTENA" and i["deteccionAnticipadaMin"] is None)),
            "reportes": glob["total"],
        },
        "zonas": zonas_out, "antenas": antenas_out[:15], "tipos": tipos, "incidentes": incidentes[-60:],
        "recurrencia": {**{k: rec_cfg[k] for k in ("umbralFallas", "ventanaDias")},
                        "ultimaEjecucion": config.leer("recurrencia", usar_cache=False).get("ultimaEjecucion"),
                        "estructurales": sum(1 for a in antenas_out if a["estructural"])},
    }


def analitica(event, context):
    try:
        dias = min(max(int((event.get("queryStringParameters") or {}).get("dias", 7)), 1), 30)
    except ValueError:
        return http.error(400, "dias debe ser un entero entre 1 y 30")
    if dias not in _cache or time.time() - _cache[dias][0] > CACHE_SEGUNDOS:
        _cache[dias] = (time.time(), _calcular(dias))
    return http.ok(_cache[dias][1])


def ejecutar_recurrencia(event, context):
    r = _sfn.start_execution(stateMachineArn=os.environ["MAQUINA_RECURRENCIA"], input=json.dumps({"origen": "manual"}))
    _cache.clear()
    return http.respuesta(202, {"ejecucionArn": r["executionArn"]})
