"""Parámetros de configuración en SSM Parameter Store: /telecorp/<stage>/<nombre> (valor JSON)."""
import json
import os
import time

import boto3

_ssm = boto3.client("ssm")
_cache: dict = {}
TTL_SEGUNDOS = 30


def ruta(nombre: str) -> str:
    return f"/telecorp/{os.environ['STAGE']}/{nombre}"


def leer(nombre: str, usar_cache: bool = True) -> dict:
    ahora = time.time()
    if usar_cache and nombre in _cache and ahora - _cache[nombre][0] < TTL_SEGUNDOS:
        return _cache[nombre][1]
    valor = json.loads(_ssm.get_parameter(Name=ruta(nombre))["Parameter"]["Value"])
    _cache[nombre] = (ahora, valor)
    return valor


def escribir(nombre: str, valor: dict) -> None:
    _ssm.put_parameter(Name=ruta(nombre), Value=json.dumps(valor), Type="String", Overwrite=True)
    _cache[nombre] = (time.time(), valor)
