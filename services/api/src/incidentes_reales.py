"""Protección de lo operativo: una simulación no puede alterar un incidente colectivo REAL abierto.

Las antenas son un solo conjunto compartido: forzar una falla (escenarios de demo o el control del simulador) cambia su estado, y el
flujo de un colectivo abierto lee ese estado para verificar la infraestructura y para decidir si el servicio se restableció. Una
Tormenta lanzada sobre una zona con un incidente real lo confirmaría con fallas que no son suyas y lo cerraría al terminar.
Por eso se rechaza (409) forzar antenas de zonas con un colectivo operativo (no simulado) abierto.
"""
from boto3.dynamodb.conditions import Attr

from telecorp import db, reglas, zonas


def abiertos_en(zona_ids) -> list:
    """Colectivos operativos abiertos en esas zonas. `zona_ids=None`: en cualquier zona."""
    abiertos = db.scan_todo(db.tabla("colectivos"), FilterExpression=Attr("estado").is_in(list(reglas.ESTADOS_COLECTIVO_ABIERTOS)))
    return [c for c in abiertos if not reglas.es_simulado(c) and (zona_ids is None or c["zonaId"] in zona_ids)]


def zonas_de_antenas(antena_ids) -> set:
    por_antena = {a["antenaId"]: a["zonaId"] for a in zonas.antenas()}
    return {por_antena[a] for a in antena_ids if a in por_antena}


def mensaje(colectivos: list) -> str:
    nombres = sorted({(zonas.zona(c["zonaId"]) or {}).get("nombre", c["zonaId"]) for c in colectivos})
    return (f"Hay un incidente real abierto en {', '.join(nombres)}: una simulación forzaría fallas de antenas que alterarían su verificación "
            "y su cierre. Elige otra zona o cierra ese incidente antes.")
