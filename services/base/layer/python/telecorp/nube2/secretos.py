"""Lectura de secretos de las integraciones desde AWS Secrets Manager (R1): `telecorp/<stage>/<nombre>`.

Un secreto JSON por nube: `azure` {acsEndpoint, acsKey, acsSender, mapsKey}, `gcp` {projectId, projectNumber, poolId,
providerId, serviceAccount, dataset} (SIN claves: federación de identidad) e `ia` {geminiApiKey, modelo}.
Caché en memoria del contenedor con TTL corto; ausencia o error → None (la integración se desactiva sin romper el flujo).
Los valores NUNCA se imprimen ni se devuelven en errores.
"""
import json
import os
import time

import boto3

TTL_SEGUNDOS = 300
TTL_NEGATIVO_SEGUNDOS = 60
_cache: dict = {}
_cliente = None


def _sm():
    global _cliente
    if _cliente is None:
        _cliente = boto3.client("secretsmanager")
    return _cliente


def id_secreto(nombre: str) -> str:
    return f"telecorp/{os.environ.get('STAGE', 'dev')}/{nombre}"


def leer(nombre: str, usar_cache: bool = True) -> dict | None:
    ahora = time.time()
    if usar_cache and nombre in _cache and _cache[nombre][0] > ahora:
        return _cache[nombre][1]
    try:
        valor = json.loads(_sm().get_secret_value(SecretId=id_secreto(nombre))["SecretString"])
        if not isinstance(valor, dict):
            raise ValueError("el secreto debe ser un objeto JSON")
        _cache[nombre] = (ahora + TTL_SEGUNDOS, valor)
        return valor
    except Exception as e:  # noqa: BLE001 - sin detalle del mensaje (podría revelar el nombre o el contenido)
        print(f"nube2: secreto '{nombre}' no disponible ({type(e).__name__})")
        _cache[nombre] = (ahora + TTL_NEGATIVO_SEGUNDOS, None)
        return None


def olvidar() -> None:
    _cache.clear()
