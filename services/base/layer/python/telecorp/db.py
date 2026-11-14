"""Acceso a las tablas de DynamoDB. Los nombres llegan por variables de entorno (TABLA_<NOMBRE>)."""
import os

import boto3

_recurso = boto3.resource("dynamodb")


def tabla(nombre: str):
    """tabla("antenas") → Table(os.environ["TABLA_ANTENAS"])."""
    return _recurso.Table(os.environ[f"TABLA_{nombre.upper()}"])


def scan_todo(t, **kwargs) -> list:
    """Scan paginado (solo para tablas pequeñas, como antenas)."""
    items, resp = [], t.scan(**kwargs)
    items.extend(resp["Items"])
    while "LastEvaluatedKey" in resp:
        resp = t.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
        items.extend(resp["Items"])
    return items
