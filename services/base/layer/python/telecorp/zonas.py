"""Catálogo de zonas y antenas.

En Lambda se lee la copia empaquetada en el layer (scripts/deploy.sh copia contracts/zonas.json).
En local o en las pruebas se usa directamente contracts/zonas.json del repo.
"""
import json
import os
from functools import lru_cache

_AQUI = os.path.dirname(__file__)
_RUTAS = [
    os.path.join(_AQUI, "zonas.json"),
    os.path.join(_AQUI, "..", "..", "..", "..", "..", "contracts", "zonas.json"),
]


@lru_cache(maxsize=1)
def catalogo() -> dict:
    for ruta in _RUTAS:
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("No se encontró zonas.json (¿se ejecutó scripts/deploy.sh?)")


def zonas() -> list:
    return catalogo()["zonas"]


def zona(zona_id: str):
    return next((z for z in zonas() if z["zonaId"] == zona_id), None)


def criticidad(zona_id: str) -> int:
    z = zona(zona_id)
    return catalogo()["tiposZona"].get(z["tipo"], 1) if z else 1


def antenas() -> list:
    """Lista plana: [{antenaId, lat, lng, zonaId}, ...]."""
    return [{**a, "zonaId": z["zonaId"]} for z in zonas() for a in z["antenas"]]


def zona_de_antena(antena_id: str):
    return next((a["zonaId"] for a in antenas() if a["antenaId"] == antena_id), None)


def distancia_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia aproximada en metros (equirectangular: suficiente a escala de ciudad)."""
    import math
    x = math.radians(lng2 - lng1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371000 * math.hypot(x, y)


def ubicar(lat: float, lng: float, tolerancia: float = 1.6):
    """Zona más cercana cuya cobertura (radio × tolerancia) contiene el punto. None si está fuera de cobertura."""
    candidatas = [(distancia_m(lat, lng, z["centro"]["lat"], z["centro"]["lng"]), z) for z in zonas()]
    candidatas = [(d, z) for d, z in candidatas if d <= z["radioM"] * tolerancia]
    if not candidatas:
        return None
    d, z = min(candidatas, key=lambda c: c[0] / c[1]["radioM"])
    return {**z, "distanciaM": round(d)}
