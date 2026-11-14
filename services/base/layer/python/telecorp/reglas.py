"""Reglas de negocio puras (sin AWS). Fuente de verdad: docs/arquitectura.md > Reglas de negocio."""

ESTADOS_ANTENA = ("INHABILITADA", "CAIDA", "NORMAL", "SATURADA")
# Orden de gravedad para resumir una zona por su peor antena (mayor = peor).
GRAVEDAD_ANTENA = {"SIN_DATOS": 0, "NORMAL": 1, "SATURADA": 2, "CAIDA": 3, "INHABILITADA": 4}


def clasificar_antena(gb_por_minuto: float) -> str:
    """0 → INHABILITADA; <60 → CAIDA; 60..129 → NORMAL; >129 → SATURADA."""
    if gb_por_minuto <= 0:
        return "INHABILITADA"
    if gb_por_minuto < 60:
        return "CAIDA"
    if gb_por_minuto > 129:
        return "SATURADA"
    return "NORMAL"


def peor_estado(estados) -> str:
    """El estado más grave de una lista (para pintar una zona). Lista vacía → SIN_DATOS."""
    return max(estados, key=lambda e: GRAVEDAD_ANTENA.get(e, 0), default="SIN_DATOS")
