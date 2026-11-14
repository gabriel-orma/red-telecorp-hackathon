"""Detector de incidentes colectivos (DynamoDB Streams).

Fuentes:
- Stream de `incidencias` (INSERT): si ya hay un colectivo abierto en la zona, la incidencia se suma. Si no, cuenta
  los usuarios DISTINTOS con incidencias activas en la zona dentro de la ventana (<24 h): con ≥10 crea el colectivo.
- Stream de `antenas` (filtrado a CAIDA / INHABILITADA): cuando una antena ENTRA en falla, detección proactiva
  (el sistema se entera antes que los usuarios), o se suma la antena al colectivo abierto.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos

import os

from boto3.dynamodb.types import TypeDeserializer

from telecorp import config, reglas, zonas
import comun_colectivos as cc  # noqa: E402

_des = TypeDeserializer()


def _imagen(registro: dict, clave: str) -> dict:
    return {k: _des.deserialize(v) for k, v in registro["dynamodb"].get(clave, {}).items()}


def nueva_incidencia(inc: dict) -> None:
    if inc.get("estado") not in reglas.ESTADOS_INCIDENCIA_ACTIVOS:
        return
    zona_id = inc["zonaId"]
    abierto = cc.colectivo_abierto(zona_id)
    if abierto:
        cc.agrupar_incidencias(cc.obtener(abierto), [inc], notificar_estado=True)
        return

    cfg = config.leer("reglas").get("colectivo", {})
    horas, umbral = int(cfg.get("ventanaHoras", 24)), int(cfg.get("umbralUsuarios", 10))
    activas = {i["incidenciaId"]: i for i in cc.incidencias_activas_zona(zona_id, horas)}
    activas[inc["incidenciaId"]] = inc  # el GSI es eventualmente consistente: incluir la recién llegada
    usuarios = {i["usuarioId"] for i in activas.values()}
    if reglas.es_colectivo(len(usuarios), umbral):
        nombre = (zonas.zona(zona_id) or {}).get("nombre", zona_id)
        cc.crear(zona_id, "REPORTES_USUARIOS", f"{len(usuarios)} usuarios distintos reportaron en {nombre} (< {horas} h)",
                 list(activas.values()), [])


def cambio_antena(anterior: dict, nueva: dict) -> None:
    if not reglas.entra_en_falla(anterior.get("estado"), nueva.get("estado")):
        return
    zona_id = nueva["zonaId"]
    antena = {"antenaId": nueva["antenaId"], "estado": nueva["estado"], "desde": nueva.get("estadoDesde") or nueva.get("actualizadoEn")}
    abierto = cc.colectivo_abierto(zona_id)
    if abierto:
        cc.agregar_antenas(cc.obtener(abierto), [antena])
        return
    horas = int(config.leer("reglas").get("colectivo", {}).get("ventanaHoras", 24))
    cc.crear(zona_id, "METRICAS_ANTENA", f"Antena {antena['antenaId']} {antena['estado']} (detección proactiva)",
             cc.incidencias_activas_zona(zona_id, horas), [antena])


def handler(event, context):
    tabla_incidencias = f"table/{os.environ['TABLA_INCIDENCIAS']}/"
    for r in event.get("Records", []):
        if tabla_incidencias in r["eventSourceARN"]:
            nueva_incidencia(_imagen(r, "NewImage"))
        else:
            cambio_antena(_imagen(r, "OldImage"), _imagen(r, "NewImage"))
    # Un error se propaga: Lambda reintenta (y parte el lote) según la configuración del stream.
