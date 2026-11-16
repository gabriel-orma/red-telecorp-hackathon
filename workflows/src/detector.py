"""Detector de incidentes colectivos (DynamoDB Streams + barrido periódico).

Fuentes:
- Stream de `incidencias` (INSERT): si ya hay un colectivo abierto en la zona, la incidencia se suma. Si no, se anota al
  usuario en la ventana atómica de la zona y se cuentan los usuarios DISTINTOS de las últimas 24 h (estrictamente
  menos de 24 h, de cualquier estado, relacionados con el servicio y aún sin colectivo): con ≥10 se crea el colectivo.
- Stream de `antenas` (solo la TRANSICIÓN a CAIDA / INHABILITADA): detección proactiva (el sistema se entera antes que
  los usuarios), o se suma la antena al colectivo abierto.
- `reconciliar` (EventBridge, cada 5 min): reevalúa cada zona y arranca la Step Function de colectivos "zombi".
  Es la red de seguridad si algún evento del stream se perdió o llegó fuera de orden.

El conteo no depende solo del GSI `zona-fecha` (eventualmente consistente): se une con la ventana de la zona
(`comun_colectivos.registrar_en_ventana`), que se escribe y se lee con consistencia fuerte.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos

import os

from boto3.dynamodb.types import TypeDeserializer

from telecorp import config, reglas, util, zonas
from telecorp.nube2 import cloudflare
import comun_colectivos as cc  # noqa: E402

_des = TypeDeserializer()


def _imagen(registro: dict, clave: str) -> dict:
    return {k: _des.deserialize(v) for k, v in registro["dynamodb"].get(clave, {}).items()}


def _parametros() -> tuple:
    cfg = config.leer("reglas").get("colectivo", {})
    return int(cfg.get("ventanaHoras", 24)), int(cfg.get("umbralUsuarios", 10))


def evaluar_zona(zona_id: str, horas: int, umbral: int, entrante: dict | None = None, ventana: dict | None = None,
                 sim: bool = False):
    """Cuenta usuarios distintos de la zona (GSI ∪ ventana atómica ∪ incidencia entrante) y crea el colectivo si
    llegan al umbral. Devuelve el id del colectivo o None. `sim`: cuenta solo reportes simulados (o solo operativos)."""
    if ventana is None:
        ventana = cc.leer_ventana(zona_id, horas, sim)
    candidatas = {i["incidenciaId"]: i for i in cc.incidencias_ventana_zona(zona_id, horas, sim) if cc.relacionada_con_servicio(i)}
    if entrante:
        candidatas[entrante["incidenciaId"]] = entrante
    usuarios = {i["usuarioId"] for i in candidatas.values()} | set(ventana)
    if not reglas.es_colectivo(len(usuarios), umbral):
        return None
    # Decisión: se confirma con las incidencias REALES (la ventana puede arrastrar rezagadas ya agrupadas o borradas).
    faltan = [e["inc"] for e in ventana.values() if e["inc"] not in candidatas]
    for i in cc.cargar_incidencias(faltan, horas):
        if cc.relacionada_con_servicio(i):
            candidatas[i["incidenciaId"]] = i
    usuarios = {i["usuarioId"] for i in candidatas.values()}
    if not reglas.es_colectivo(len(usuarios), umbral):
        return None
    nombre = (zonas.zona(zona_id) or {}).get("nombre", zona_id)
    return cc.crear(zona_id, "REPORTES_USUARIOS", f"{len(usuarios)} usuarios distintos reportaron en {nombre} (< {horas} h)",
                    list(candidatas.values()), [], consumidos=ventana, simulado=sim)


def nueva_incidencia(inc: dict) -> None:
    if inc.get("estado") not in reglas.ESTADOS_INCIDENCIA_ACTIVOS:
        return
    zona_id = inc["zonaId"]
    sim = reglas.es_simulado(inc)   # cada modo cuenta aparte: un reporte simulado no suma a lo real ni al revés
    abierto = cc.colectivo_abierto(zona_id, sim)
    if abierto:
        cc.unir(abierto, [inc], [])  # suma la incidencia y cura un colectivo sin Step Function
        return
    horas, umbral = _parametros()
    if not cc.relacionada_con_servicio(inc):  # H11: un reporte "OTRO" no dispara colectivos por sí solo
        return
    if inc["creadaEn"] <= util.hace_iso(hours=horas):  # H09: reproceso tardío (p. ej. desde la DLQ) fuera de la ventana
        return
    ventana = cc.registrar_en_ventana(zona_id, inc, horas, sim)
    evaluar_zona(zona_id, horas, umbral, entrante=inc, ventana=ventana, sim=sim)


def cambio_antena(anterior: dict, nueva: dict) -> None:
    if not reglas.entra_en_falla(anterior.get("estado"), nueva.get("estado")):
        return
    zona_id = nueva["zonaId"]
    sim = reglas.es_simulado(nueva)   # `simulada`: el simulador marca las fallas forzadas (en operación normal no existen)
    antena = {"antenaId": nueva["antenaId"], "estado": nueva["estado"], "desde": nueva.get("estadoDesde") or nueva.get("actualizadoEn")}
    abierto = cc.colectivo_abierto(zona_id, sim)
    if abierto:
        cc.unir(abierto, [], [antena])
        return
    horas, _ = _parametros()
    cc.crear(zona_id, "METRICAS_ANTENA", f"Antena {antena['antenaId']} {antena['estado']} (detección proactiva)"
             + (" · simulada" if sim else ""), cc.incidencias_activas_zona(zona_id, horas, sim), [antena], simulado=sim)


def reconciliar(event, context) -> dict:
    """Barrido periódico (H08): reevalúa cada zona y arranca la Step Function de los colectivos que no la tengan."""
    horas, umbral = _parametros()
    creados, curados = [], []
    for z in zonas.zonas():
        for sim in (False, True):   # lo operativo y lo simulado se reevalúan por separado
            abierto = cc.colectivo_abierto(z["zonaId"], sim)
            if abierto:
                col = cc.obtener(abierto)
                if not col.get("ejecucionArn"):
                    cc.asegurar_ejecucion(col)
                    curados.append(abierto)
                continue
            nuevo = evaluar_zona(z["zonaId"], horas, umbral, sim=sim)
            if nuevo:
                creados.append(nuevo)
    print(f"reconciliar: {len(creados)} colectivos creados, {len(curados)} curados")
    # Tercera nube (D15): el mismo barrido publica el estado público en Cloudflare (sin Lambda nueva, D14). Nunca lanza.
    espejo = cloudflare.publicar()
    return {"creados": creados, "curados": curados, "espejo": espejo}


def handler(event, context):
    tabla_incidencias = f"table/{os.environ['TABLA_INCIDENCIAS']}/"
    for r in event.get("Records", []):
        if tabla_incidencias in r["eventSourceARN"]:
            nueva_incidencia(_imagen(r, "NewImage"))
        else:
            cambio_antena(_imagen(r, "OldImage"), _imagen(r, "NewImage"))
    # Un error se propaga: Lambda reintenta (y parte el lote) según la configuración del stream.
