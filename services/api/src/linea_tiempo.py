"""Línea de tiempo del centro de control (estilo editor de video).

GET /api/linea-tiempo?horas=1 → todo lo necesario para "rebobinar" la red en el navegador:
  - reportes: cada reporte con su instante, zona, tipo y punto (mapa de calor en el tiempo);
  - antenas: estado al inicio de la ventana + cambios de estado (del historial inmutable);
  - colectivos: intervalo de vida, cambios de estado y de prioridad.
El navegador calcula el estado de la red en cualquier instante t con búsqueda binaria; el servidor no
repite consultas por cada movimiento del cabezal.

Costo: 12 consultas (una por zona, GSI zona-fecha) + 36 (historial de cada antena) + una por colectivo
de la ventana, en paralelo. Solo operadores (JWT + grupo). Con caché de 2 s para que varios paneles en vivo no multipliquen lecturas.
"""
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import boto3
from boto3.dynamodb.types import TypeDeserializer

from telecorp import http, util, zonas

sys.path.insert(0, os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos
import acceso  # noqa: E402

_cliente = boto3.client("dynamodb")  # los clientes de boto3 sí se pueden usar desde varios hilos
_des = TypeDeserializer()
_cache: dict = {}
CACHE_S = 2.0
MAX_REPORTES = 6000
NIVELES = ("BAJA", "MEDIA", "ALTA", "CRITICA")


def _tabla(nombre: str) -> str:
    return os.environ[f"TABLA_{nombre.upper()}"]


def _py(item: dict) -> dict:
    return {k: _des.deserialize(v) for k, v in item.items()}


def _consultar(**kwargs) -> list:
    salida = []
    for pagina in _cliente.get_paginator("query").paginate(**kwargs):
        salida.extend(_py(i) for i in pagina["Items"])
    return salida


def _escanear(**kwargs) -> list:
    salida = []
    for pagina in _cliente.get_paginator("scan").paginate(**kwargs):
        salida.extend(_py(i) for i in pagina["Items"])
    return salida


def _reportes_zona(zona_id: str, desde: str, hasta: str) -> list:
    return _consultar(TableName=_tabla("incidencias"), IndexName="zona-fecha",
                      KeyConditionExpression="zonaId = :z AND creadaEn BETWEEN :d AND :h",
                      ExpressionAttributeValues={":z": {"S": zona_id}, ":d": {"S": desde}, ":h": {"S": hasta}},
                      ProjectionExpression="incidenciaId, creadaEn, zonaId, tipo, reporte.ubicacion")


def _historial(entidad_id: str, desde: str, hasta: str) -> list:
    return _consultar(TableName=_tabla("historial"),
                      KeyConditionExpression="entidadId = :e AND sk BETWEEN :d AND :h",
                      ExpressionAttributeValues={":e": {"S": entidad_id}, ":d": {"S": desde}, ":h": {"S": hasta + "~"}})


# ---------------- Lógica pura (probada en tests) ----------------

def nivel_de(detalle: str) -> str | None:
    """'ALTA (puntaje 54)' → ALTA; 'Re-priorizado: MEDIA → CRITICA (puntaje 120)' → CRITICA (el último nivel)."""
    encontrados = re.findall(r"\b(BAJA|MEDIA|ALTA|CRITICA)\b", detalle or "")
    return encontrados[-1] if encontrados else None


def pista_antena(antena: dict, eventos: list, estado_actual: str | None) -> dict:
    """Estado al inicio de la ventana + cambios ordenados. Sin cambios en la ventana → el estado actual todo el tiempo."""
    cambios = sorted((e for e in eventos if e.get("tipoEvento") == "CAMBIO_ESTADO" and e.get("estadoNuevo")),
                     key=lambda e: e["ocurridoEn"])
    inicial = (cambios[0].get("estadoAnterior") if cambios else estado_actual) or "SIN_DATOS"
    return {"antenaId": antena["antenaId"], "zonaId": antena["zonaId"], "inicial": inicial,
            "cambios": [{"t": e["ocurridoEn"], "estado": e["estadoNuevo"]} for e in cambios]}


def pista_colectivo(col: dict, eventos: list) -> dict:
    ordenados = sorted(eventos, key=lambda e: e["ocurridoEn"])
    estados = [{"t": e["ocurridoEn"], "estado": e["estadoNuevo"]} for e in ordenados
               if e.get("tipoEvento") in ("CREADO", "CAMBIO_ESTADO") and e.get("estadoNuevo")]
    if not estados:
        estados = [{"t": col["detectadoEn"], "estado": "EN_EVALUACION"}]
    prioridades = [{"t": e["ocurridoEn"], "prioridad": n} for e in ordenados
                   if e.get("tipoEvento") == "PRIORIDAD_ASIGNADA" and (n := nivel_de(e.get("detalle", "")))]
    zona = zonas.zona(col["zonaId"]) or {}
    return {"id": col["incidenteColectivoId"], "zonaId": col["zonaId"], "zonaNombre": zona.get("nombre", col["zonaId"]),
            "origen": col.get("origen"), "inicio": col["detectadoEn"], "fin": col.get("resueltoEn"),
            "prioridad": col.get("prioridad", "BAJA"), "afectados": len(col.get("usuariosAfectados") or []),
            "estados": estados, "prioridades": prioridades}


def punto_reporte(inc: dict) -> dict:
    u = (inc.get("reporte") or {}).get("ubicacion") or {}
    punto = {"id": inc["incidenciaId"], "t": inc["creadaEn"], "zonaId": inc["zonaId"], "tipo": inc.get("tipo")}
    if u.get("lat") is not None and u.get("lng") is not None:
        punto.update(lat=float(u["lat"]), lng=float(u["lng"]))
    return punto


def se_cruza(col: dict, desde: str, hasta: str) -> bool:
    return col["detectadoEn"] <= hasta and (not col.get("resueltoEn") or col["resueltoEn"] >= desde)


# ---------------- Handler ----------------

def armar(horas: float) -> dict:
    ahora = util.ahora()
    hasta, desde = util.iso(ahora), util.iso(ahora - timedelta(hours=horas))
    antenas = zonas.antenas()
    with ThreadPoolExecutor(max_workers=16) as pool:
        f_reportes = [pool.submit(_reportes_zona, z["zonaId"], desde, hasta) for z in zonas.zonas()]
        f_antenas = {a["antenaId"]: pool.submit(_historial, a["antenaId"], desde, hasta) for a in antenas}
        f_actuales = pool.submit(_escanear, TableName=_tabla("antenas"), ProjectionExpression="antenaId, estado")
        f_colectivos = pool.submit(_escanear, TableName=_tabla("colectivos"),
                                   ProjectionExpression="incidenteColectivoId, zonaId, origen, detectadoEn, resueltoEn, "
                                                        "prioridad, usuariosAfectados")
        colectivos = [c for c in f_colectivos.result() if se_cruza(c, desde, hasta)]
        f_hist_col = {c["incidenteColectivoId"]: pool.submit(_historial, c["incidenteColectivoId"], "0", hasta)
                      for c in colectivos}
        reportes = sorted((punto_reporte(i) for f in f_reportes for i in f.result()), key=lambda r: r["t"])[-MAX_REPORTES:]
        actuales = {a["antenaId"]: a.get("estado") for a in f_actuales.result()}
        pistas_antenas = [pista_antena(a, f_antenas[a["antenaId"]].result(), actuales.get(a["antenaId"])) for a in antenas]
        pistas_col = sorted((pista_colectivo(c, f_hist_col[c["incidenteColectivoId"]].result()) for c in colectivos),
                            key=lambda c: c["inicio"])
    return {"desde": desde, "hasta": hasta, "horas": horas, "generadoEn": util.ahora_iso(),
            "reportes": reportes, "antenas": pistas_antenas, "colectivos": pistas_col}


@acceso.solo_operadores  # incluye el punto GPS de cada reporte: solo operadores
def linea_tiempo(event, context):
    q = event.get("queryStringParameters") or {}
    try:
        horas = min(max(float(q.get("horas", 1)), 0.1), 24.0)
    except ValueError:
        return http.error(400, "horas debe ser un número entre 0.1 y 24")
    clave, ahora = round(horas, 2), time.time()
    if clave in _cache and ahora - _cache[clave][0] < CACHE_S:
        return http.ok(_cache[clave][1])
    datos = armar(horas)
    _cache[clave] = (ahora, datos)
    return http.ok(datos)
