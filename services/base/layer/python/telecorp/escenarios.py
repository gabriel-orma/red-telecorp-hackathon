"""Escenarios de demo (E5): tormenta y corte de energía. Lógica pura (sin AWS) para poder probarla.

Un escenario se ejecuta en OLEADAS espaciadas en el tiempo. Cada oleada:
- fuerza fallas en algunas antenas (vía las fallas del simulador), y
- genera reportes de usuarios ficticios en las zonas afectadas.
La Step Function `escenario` recorre las oleadas con un Map secuencial + Wait.
"""
import math
import random

TIPOS = {
    # Tormenta: la zona central y sus vecinas; antenas caen o se saturan, muchos reportes.
    "TORMENTA": {"radioVecinasM": 5500, "oleadas": 5, "reportesPorOleada": (4, 7), "falla": ("CAIDA", "SATURADA")},
    # Corte de energía: solo la zona elegida; sus antenas se apagan una por una.
    "CORTE_ENERGIA": {"radioVecinasM": 0, "oleadas": 4, "reportesPorOleada": (3, 5), "falla": ("INHABILITADA",)},
}
GB_POR_FALLA = {"CAIDA": 30.0, "SATURADA": 150.0, "INHABILITADA": 0.0}
SEGUNDOS_ENTRE_OLEADAS = 12
TIPOS_REPORTE = {
    "TORMENTA": ["SIN_INTERNET", "INTERMITENCIA", "SIN_SENAL", "INTERNET_LENTO", "SIN_LLAMADAS"],
    "CORTE_ENERGIA": ["SIN_SENAL", "SIN_INTERNET", "SIN_LLAMADAS"],
}


def _distancia_m(a: dict, b: dict) -> float:
    x = math.radians(b["lng"] - a["lng"]) * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    y = math.radians(b["lat"] - a["lat"])
    return 6371000 * math.hypot(x, y)


def zonas_afectadas(tipo: str, zona_id: str, zonas: list) -> list:
    """La zona elegida primero y luego las vecinas dentro del radio del escenario (ordenadas por cercanía)."""
    centro = next(z for z in zonas if z["zonaId"] == zona_id)
    radio = TIPOS[tipo]["radioVecinasM"]
    vecinas = sorted(
        (z for z in zonas if z["zonaId"] != zona_id and _distancia_m(centro["centro"], z["centro"]) <= radio),
        key=lambda z: _distancia_m(centro["centro"], z["centro"]),
    )
    return [centro] + vecinas


def planificar(tipo: str, zona_id: str, zonas: list, semilla: int | None = None) -> list:
    """Lista de oleadas: [{n, esperaSegundos, fallas: {antenaId: gb}, reportes: [{zonaId, tipo}]}].

    La zona elegida recibe la mayor parte de los reportes (para que supere el umbral de 10 usuarios);
    las vecinas reciben menos, como pasa con un fenómeno real que se expande.
    """
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de escenario desconocido: {tipo}")
    cfg = TIPOS[tipo]
    rng = random.Random(semilla)
    afectadas = zonas_afectadas(tipo, zona_id, zonas)
    antenas = [(z["zonaId"], a["antenaId"]) for z in afectadas for a in z["antenas"]]
    # Primero caen las de la zona central; las vecinas después.
    oleadas = []
    for n in range(cfg["oleadas"]):
        cuantas = max(1, math.ceil(len(antenas) / cfg["oleadas"]))
        lote = antenas[n * cuantas:(n + 1) * cuantas]
        fallas = {}
        for _, antena_id in lote:
            estado = rng.choice(cfg["falla"])
            fallas[antena_id] = GB_POR_FALLA[estado]
        reportes = []
        for _ in range(rng.randint(*cfg["reportesPorOleada"])):
            zona = afectadas[0] if rng.random() < 0.75 or len(afectadas) == 1 else rng.choice(afectadas[1:])
            reportes.append({"zonaId": zona["zonaId"], "tipo": rng.choice(TIPOS_REPORTE[tipo])})
        oleadas.append({"n": n + 1, "total": cfg["oleadas"], "esperaSegundos": 0 if n == 0 else SEGUNDOS_ENTRE_OLEADAS,
                        "fallas": fallas, "reportes": reportes})
    return oleadas


def reporte_simulado(zona: dict, tipo: str, rng: random.Random) -> dict:
    """Reporte de un vecino ficticio (marcado `simulado`), con un punto al azar dentro de la zona."""
    dni = str(rng.randint(90_000_000, 99_999_999))
    ang, dist = rng.uniform(0, 2 * math.pi), zona["radioM"] * math.sqrt(rng.random()) * 0.85
    lat = zona["centro"]["lat"] + dist * math.sin(ang) / 111320
    lng = zona["centro"]["lng"] + dist * math.cos(ang) / (111320 * math.cos(math.radians(zona["centro"]["lat"])))
    descripciones = {
        "SIN_INTERNET": "Me quedé sin Internet de golpe", "INTERMITENCIA": "La señal va y viene con la tormenta",
        "SIN_SENAL": "El celular dice sin servicio", "INTERNET_LENTO": "Todo carga lentísimo",
        "SIN_LLAMADAS": "No puedo hacer llamadas",
    }
    return {
        "usuarioId": dni, "nombre": f"Vecino simulado {dni[-3:]}", "numeroServicio": f"9{dni}",
        "email": f"sim.{dni}@example.com", "zonaId": zona["zonaId"], "ubicacionFuente": "GPS",
        "ubicacion": {"lat": round(lat, 6), "lng": round(lng, 6)}, "tipo": tipo,
        "descripcion": descripciones.get(tipo, "Problema con el servicio"), "avisarPorEmail": False, "simulado": True,
    }
