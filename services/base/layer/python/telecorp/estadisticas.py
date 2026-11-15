"""Estadísticas de reportes para la página pública de estado (E3.5, decisión D10).

En lugar de escanear incidencias, el worker incrementa contadores agregados por bloque de 15 minutos:
  tabla `estadisticas`: PK serie ("GLOBAL" o "ZONA-xx"), SK bucket ("2026-11-14T10:15:00Z"),
  atributos total y t_<TIPO> (ADD atómico), TTL 35 días.
Leer 24 h son 96 ítems por serie, sin importar cuántos millones de reportes haya.
"""
from datetime import datetime, timedelta, timezone

MINUTOS_BUCKET = 15
BUCKETS_DIA = 24 * 60 // MINUTOS_BUCKET  # 96
DIAS_BASE = 7
TTL_DIAS = 35


def bucket(dt: datetime) -> str:
    """Inicio del bloque de 15 min que contiene `dt`, en ISO UTC."""
    dt = dt.astimezone(timezone.utc).replace(second=0, microsecond=0)
    dt -= timedelta(minutes=dt.minute % MINUTOS_BUCKET)
    return dt.strftime("%Y-%m-%dT%H:%M:00Z")


def bucket_de_iso(texto: str) -> str:
    return bucket(datetime.fromisoformat(texto.replace("Z", "+00:00")))


def buckets_ultimas_24h(ahora: datetime) -> list:
    """Los 96 bloques que terminan en el actual (orden cronológico)."""
    actual = datetime.fromisoformat(bucket(ahora).replace("Z", "+00:00"))
    return [bucket(actual - timedelta(minutes=MINUTOS_BUCKET * i)) for i in range(BUCKETS_DIA - 1, -1, -1)]


def linea_base(conteos: dict, b: str, dias: int = DIAS_BASE) -> float:
    """Promedio de reportes en el MISMO bloque horario de los `dias` días previos (lo "normal" a esa hora)."""
    t = datetime.fromisoformat(b.replace("Z", "+00:00"))
    valores = [conteos.get(bucket(t - timedelta(days=d)), 0) for d in range(1, dias + 1)]
    return round(sum(valores) / dias, 2)


def nivel(ultima_hora: int, base_hora: float, hay_colectivo: bool) -> str:
    """Semáforo del estado de la red.

    PROBLEMAS: hay un incidente colectivo activo (confirmado por la plataforma).
    POSIBLES_PROBLEMAS: pico de reportes en la última hora (≥5 y más de 3 veces lo normal).
    """
    if hay_colectivo:
        return "PROBLEMAS"
    if ultima_hora >= 5 and ultima_hora > 3 * max(base_hora, 1):
        return "POSIBLES_PROBLEMAS"
    return "SIN_PROBLEMAS"


MENSAJES = {
    "SIN_PROBLEMAS": "Los reportes de usuarios no indican problemas en la red.",
    "POSIBLES_PROBLEMAS": "Los reportes indican posibles problemas. Lo estamos revisando.",
    "PROBLEMAS": "Hay un incidente confirmado. Nuestro equipo ya está trabajando.",
}


def argumentos_incremento(serie: str, b: str, tipo: str, ttl_epoch: int) -> dict:
    """Argumentos del Update que suma 1 al total y al tipo del bloque (sirven para update_item o para una transacción)."""
    return dict(
        Key={"serie": serie, "bucket": b},
        UpdateExpression="ADD #total :uno, #tipo :uno SET expiraEn = if_not_exists(expiraEn, :ttl)",
        ExpressionAttributeNames={"#total": "total", "#tipo": f"t_{tipo}"},
        ExpressionAttributeValues={":uno": 1, ":ttl": ttl_epoch},
    )


def incrementar(tabla, serie: str, b: str, tipo: str, ttl_epoch: int) -> None:
    """Suma 1 al total y al tipo del bloque (atómico, sin leer antes)."""
    tabla.update_item(**argumentos_incremento(serie, b, tipo, ttl_epoch))
