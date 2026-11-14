"""Regla PURA de recurrencia (problema estructural): una antena que "se recupera" pero vuelve a fallar en días distintos.

Un episodio = un incidente colectivo en cuya lista `antenasEnFalla` figura la antena (los parpadeos dentro del mismo
colectivo ya cuentan como UN solo episodio). Una antena es ESTRUCTURAL si en los últimos `ventana_dias` tiene al menos
`min_episodios` episodios repartidos en al menos `min_dias` días calendario distintos (hora de Lima por defecto).

Umbrales provisionales (D7): se ajustan en SSM `reglas.recurrencia` sin tocar código. Sin AWS: se prueba con casos límite.
La máquina `recurrencia-diaria` (EventBridge Scheduler → Lambda → esta regla → marcar) está PENDIENTE: ver workflows/README.md.
"""
from datetime import datetime, timedelta, timezone


def _parsear(ts: str) -> datetime:
    d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def evaluar_recurrencia(episodios: list, ahora: datetime, ventana_dias: int = 30, min_episodios: int = 3,
                        min_dias: int = 2, huso_horas: int = -5) -> dict:
    """`episodios`: [{"antenaId": ..., "ts": iso8601}]. Devuelve {antenaId: {"episodios", "dias", "estructural"}}.

    La ventana es (ahora - ventana_dias, ahora]: un episodio de hace exactamente `ventana_dias` NO cuenta; los futuros tampoco.
    """
    huso = timezone(timedelta(hours=huso_horas))
    desde = ahora - timedelta(days=ventana_dias)
    por_antena: dict = {}
    for e in episodios:
        t = _parsear(e["ts"])
        if desde < t <= ahora:
            por_antena.setdefault(e["antenaId"], []).append(t.astimezone(huso).date())
    return {a: {"episodios": len(dias), "dias": len(set(dias)),
                "estructural": len(dias) >= min_episodios and len(set(dias)) >= min_dias}
            for a, dias in por_antena.items()}
