"""Utilidades sin dependencias de AWS."""
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

_B36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    """ISO 8601 UTC con milisegundos y sufijo Z. Se puede ordenar como texto."""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def ahora_iso() -> str:
    return iso(ahora())


def hace_iso(**delta) -> str:
    """Ej.: hace_iso(minutes=30)."""
    return iso(ahora() - timedelta(**delta))


def parse_iso(texto: str) -> datetime:
    return datetime.fromisoformat(texto.replace("Z", "+00:00"))


def nuevo_id(prefijo: str) -> str:
    """Id ordenable por tiempo: <PREFIJO>-<ms en base 36><aleatorio>."""
    ms, b36 = int(time.time() * 1000), ""
    while ms:
        ms, r = divmod(ms, 36)
        b36 = _B36[r] + b36
    return f"{prefijo}-{b36}{secrets.token_hex(3).upper()}"


def a_dynamo(valor):
    """Convierte floats a Decimal (DynamoDB no acepta float)."""
    return json.loads(json.dumps(valor), parse_float=Decimal)


def desde_dynamo(valor):
    """Convierte Decimal a int/float y sets a listas, para poder serializar a JSON."""
    if isinstance(valor, list):
        return [desde_dynamo(v) for v in valor]
    if isinstance(valor, set):
        return sorted(desde_dynamo(v) for v in valor)
    if isinstance(valor, dict):
        return {k: desde_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    return valor
