"""Pasos de la Step Function `recurrencia` (E6): antenas con fallas repetidas → problema estructural.

Datos simulados (fallas forzadas del simulador) y operativos se evalúan por separado: la ejecución diaria mira solo lo
operativo; la manual puede pedir `simulados: true` (se marca la antena como estructural-simulada y NO se alerta al NOC).

Una antena que cae varias veces y "se recupera" sola puede esconder un problema de fondo (hardware, energía,
enlace). Si entra en falla `umbralFallas` veces dentro de `ventanaDias` (TODO D7: 3 en 7 días, en SSM),
se marca como ESTRUCTURAL y se alerta al NOC para mantenimiento especializado.
"""
import os

import boto3
from boto3.dynamodb.conditions import Key

from telecorp import config, db, historial, reglas, util, zonas

_sns = boto3.client("sns")


def _cfg() -> dict:
    return {"umbralFallas": 3, "ventanaDias": 7, **config.leer("reglas").get("recurrencia", {})}


def contar(event, context):
    """Cuenta las entradas en falla de cada antena en la ventana; desmarca las que ya no superan el umbral."""
    cfg = _cfg()
    simulados = bool((event or {}).get("simulados"))
    desde = util.hace_iso(days=cfg["ventanaDias"])
    hist, antenas = db.tabla("historial"), db.tabla("antenas")
    estructurales, desmarcadas = [], 0
    for a in zonas.antenas():
        eventos = hist.query(KeyConditionExpression=Key("entidadId").eq(a["antenaId"]) & Key("sk").gte(desde))["Items"]
        fallas = reglas.contar_fallas(eventos, desde, simulados)
        if reglas.es_estructural(fallas, cfg):
            estructurales.append({"antenaId": a["antenaId"], "zonaId": a["zonaId"], "fallas": fallas,
                                  "ventanaDias": cfg["ventanaDias"], "simulado": simulados})
        else:
            actual = antenas.get_item(Key={"antenaId": a["antenaId"]}).get("Item", {})
            # Solo se desmarca lo que esta ejecución puede juzgar: la marca del otro universo no se toca.
            if actual.get("estructural") and reglas.es_simulado(actual["estructural"]) == simulados:
                antenas.update_item(Key={"antenaId": a["antenaId"]}, UpdateExpression="REMOVE estructural")
                historial.registrar(a["antenaId"], "ANTENA", "COMENTARIO", "STEP_FUNCTION",
                                    detalle=f"Ya no es estructural: {fallas} falla(s) en {cfg['ventanaDias']} días")
                desmarcadas += 1
    return {"estructurales": estructurales, "evaluadas": len(zonas.antenas()), "desmarcadas": desmarcadas,
            "hay": bool(estructurales), "umbralFallas": cfg["umbralFallas"], "simulados": simulados}


def marcar(event, context):
    """Una iteración del Map: marca la antena; si es nueva como estructural, historial + alerta al NOC."""
    t = db.tabla("antenas")
    actual = t.get_item(Key={"antenaId": event["antenaId"]}).get("Item", {})
    simulado = bool(event.get("simulado"))
    previa = actual.get("estructural") or {}
    if previa and reglas.es_simulado(previa) != simulado:
        previa = {}   # la marca previa es del otro universo: esta ejecución la reemplaza como si fuera nueva
    estructural = {"desde": previa.get("desde") or util.ahora_iso(), "fallas": event["fallas"], "ventanaDias": event["ventanaDias"],
                   **({"simulado": True} if simulado else {})}
    t.update_item(Key={"antenaId": event["antenaId"]}, UpdateExpression="SET estructural = :e",
                  ExpressionAttributeValues={":e": estructural})
    if previa:
        return {"antenaId": event["antenaId"], "nueva": False}
    zona = (zonas.zona(event["zonaId"]) or {}).get("nombre", event["zonaId"])
    detalle = f"{event['fallas']} fallas en {event['ventanaDias']} días: requiere mantenimiento especializado"
    historial.registrar(event["antenaId"], "ANTENA", "MARCADO_ESTRUCTURAL", "STEP_FUNCTION",
                        detalle=detalle + (" (simulado)" if simulado else ""), simulado=simulado)
    if os.environ.get("TOPICO_ALERTAS") and not simulado:   # una simulación nunca despierta al NOC
        _sns.publish(TopicArn=os.environ["TOPICO_ALERTAS"], Subject="Red TeleCorp - Problema estructural en antena",
                     Message=f"{event['antenaId']} ({zona}): {detalle}.")
    return {"antenaId": event["antenaId"], "nueva": True}


def resumen(event, context):
    estado = {"ultimaEjecucion": util.ahora_iso(), "estructurales": len(event.get("conteo", {}).get("estructurales", [])),
              "evaluadas": event.get("conteo", {}).get("evaluadas", 0)}
    config.escribir("recurrencia", estado)
    return estado
