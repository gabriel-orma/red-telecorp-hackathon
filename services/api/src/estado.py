"""Estado público de la red, estilo Downdetector (E3.5). Contrato: contracts/schemas/estado-red.schema.json

GET /api/estado?zonaId=ZONA-05   (sin zonaId → GLOBAL)
GET /api/config                  → ids públicos de Cognito para el frontend
"""
import os
import time

from telecorp import estado_red, http, zonas

_cache: dict = {}
CACHE_SEGUNDOS = 10
_calcular = estado_red.calcular   # nombre anterior (pruebas)


def estado(event, context):
    alcance = (event.get("queryStringParameters") or {}).get("zonaId") or "GLOBAL"
    if alcance != "GLOBAL" and not zonas.zona(alcance):
        return http.error(404, f"Zona desconocida: {alcance}")
    ahora = time.time()
    if alcance not in _cache or ahora - _cache[alcance][0] > CACHE_SEGUNDOS:
        _cache[alcance] = (ahora, estado_red.calcular(alcance))
    respuesta = http.ok(_cache[alcance][1])
    respuesta["headers"]["cache-control"] = f"public, max-age={CACHE_SEGUNDOS}"
    return respuesta


def config(event, context):
    return http.ok({"region": os.environ.get("AWS_REGION", "us-east-1"),
                    "userPoolId": os.environ["USER_POOL_ID"], "clientId": os.environ["USER_POOL_CLIENT_ID"],
                    "wsUrl": os.environ.get("WS_URL")})
