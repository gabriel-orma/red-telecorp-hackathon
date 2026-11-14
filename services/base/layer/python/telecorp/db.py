"""Acceso a las tablas de DynamoDB. Los nombres llegan por variables de entorno (TABLA_<NOMBRE>)."""
import os

import boto3
from botocore.exceptions import ClientError

_recurso = boto3.resource("dynamodb")


def tabla(nombre: str):
    """tabla("antenas") → Table(os.environ["TABLA_ANTENAS"])."""
    return _recurso.Table(os.environ[f"TABLA_{nombre.upper()}"])


def nombre_tabla(nombre: str) -> str:
    return os.environ[f"TABLA_{nombre.upper()}"]


def clave_dedup_usuario(usuario_id: str, zona_id: str) -> str:
    """Clave de la tabla `dedup` para "este usuario ya reportó en esta zona". El prefijo `USR#` la separa de los
    candados (`LOCK#`) y las ventanas (`VENTANA#`) que viven en la misma tabla: ningún usuarioId puede pisarlos."""
    return f"USR#{usuario_id}#{zona_id}"


def scan_todo(t, **kwargs) -> list:
    """Scan paginado (solo para tablas pequeñas, como antenas)."""
    items, resp = [], t.scan(**kwargs)
    items.extend(resp["Items"])
    while "LastEvaluatedKey" in resp:
        resp = t.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **kwargs)
        items.extend(resp["Items"])
    return items


def transaccion(operaciones: list) -> None:
    """TransactWriteItems atómico (todo o nada) entre tablas. Acepta tipos de Python (str, int, list, dict, Decimal).

    `operaciones`: lista de (acción, tabla_lógica, argumentos) con acción en {"Put", "Update", "Delete", "ConditionCheck"}.
    Si alguna condición falla lanza ClientError(TransactionCanceledException); usa `motivos_cancelacion`.
    """
    items = [{accion: {"TableName": nombre_tabla(t), **kw}} for accion, t, kw in operaciones]
    _recurso.meta.client.transact_write_items(TransactItems=items)


def motivos_cancelacion(error: ClientError) -> list:
    """Motivo por operación de una transacción cancelada ('None' = la operación estaba bien)."""
    return [r.get("Code") for r in error.response.get("CancellationReasons", [])]


def es_transaccion_cancelada(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") == "TransactionCanceledException"


def obtener_varios(nombre: str, clave: str, ids: list) -> list:
    """BatchGetItem consistente por clave simple. Devuelve los ítems que existen (reintenta los no procesados)."""
    t, salida, pendientes = nombre_tabla(nombre), [], list(dict.fromkeys(ids))
    while pendientes:
        lote, pendientes = pendientes[:100], pendientes[100:]
        pedido = {t: {"Keys": [{clave: i} for i in lote], "ConsistentRead": True}}
        for _ in range(5):
            r = _recurso.batch_get_item(RequestItems=pedido)
            salida.extend(r["Responses"].get(t, []))
            pedido = r.get("UnprocessedKeys") or {}
            if not pedido:
                break
    return salida
