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
    # Simulación acelerada: ~3 min con 4 eventos encadenados en zonas distintas (ver planificar_acelerada).
    "ACELERADA": {"radioVecinasM": 0, "oleadas": 60, "reportesPorOleada": (0, 0), "falla": ("CAIDA",)},
}
SEGUNDOS_PASO_ACELERADA = 3
# En la simulación acelerada, 1 s real cuenta como 1 min para la prioridad (el puntaje sube con las horas activo).
FACTOR_TIEMPO_ACELERADA = 60
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
    if tipo == "ACELERADA":
        return planificar_acelerada(zona_id, zonas, semilla)
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


# Guion de la simulación acelerada: (paso de inicio, cómo empieza, falla, reportes, paso de recuperación).
# - ANTENA: la antena cae primero → detección proactiva; los reportes llegan después y se suman.
# - REPORTES: primero los vecinos (≥10 usuarios → colectivo por reportes); la antena cae después (correlación).
_GUION_ACELERADA = [
    {"inicio": 1, "modo": "ANTENA", "falla": "CAIDA", "reportes": 15, "recupera": 26, "titulo": "Caída de antena"},
    {"inicio": 9, "modo": "REPORTES", "falla": "CAIDA", "reportes": 14, "recupera": 36, "titulo": "Ola de reportes"},
    {"inicio": 22, "modo": "ANTENA", "falla": "INHABILITADA", "reportes": 13, "recupera": 46, "titulo": "Corte de energía"},
    {"inicio": 33, "modo": "REPORTES", "falla": "CAIDA", "reportes": 16, "recupera": 55, "titulo": "Tormenta local"},
]
_PROB_RUIDO = 0.35  # reportes sueltos en otras zonas (no llegan al umbral: van a la cola individual)


def planificar_acelerada(zona_id: str, zonas: list, semilla: int | None = None) -> list:
    """60 pasos de 3 s (~3 min). La zona elegida abre el primer evento; las demás se eligen lejos entre sí.

    Cada paso: {n, total, esperaSegundos, fallas: {antenaId: gb}, recuperar: [antenaId], reportes: [...], narrativa}.
    Todos los reportes de un evento llegan ANTES de su recuperación (si no, abrirían un colectivo nuevo).
    """
    rng = random.Random(semilla)
    total = TIPOS["ACELERADA"]["oleadas"]
    elegida = next(z for z in zonas if z["zonaId"] == zona_id)
    # Zonas de los eventos: la elegida y luego, en orden, la más lejana a las ya usadas (que no se pisen).
    usadas = [elegida]
    while len(usadas) < len(_GUION_ACELERADA):
        resto = [z for z in zonas if z not in usadas]
        usadas.append(max(resto, key=lambda z: min(_distancia_m(z["centro"], u["centro"]) for u in usadas) + rng.random()))

    pasos = [{"n": n + 1, "total": total, "esperaSegundos": 0 if n == 0 else SEGUNDOS_PASO_ACELERADA,
              "fallas": {}, "recuperar": [], "reportes": [], "narrativa": None} for n in range(total)]
    tipos = TIPOS_REPORTE["TORMENTA"]
    for guion, zona in zip(_GUION_ACELERADA, usadas):
        antenas = [a["antenaId"] for a in zona["antenas"]]
        caen = antenas[:2] if guion["falla"] == "CAIDA" else antenas  # el corte de energía apaga toda la zona
        inicio, recupera = guion["inicio"], guion["recupera"]
        paso_falla = inicio if guion["modo"] == "ANTENA" else inicio + 7
        for k, antena_id in enumerate(caen):  # en cascada, una por paso
            pasos[min(paso_falla + k, total) - 1]["fallas"][antena_id] = GB_POR_FALLA[guion["falla"]]
        pasos[recupera - 1]["recuperar"].extend(caen)
        # Reportes: repartidos entre el inicio y 3 pasos antes de la recuperación, más densos al principio.
        desde = inicio + (1 if guion["modo"] == "ANTENA" else 0)
        hasta = min(recupera - 3, desde + 12)
        for _ in range(guion["reportes"]):
            paso = desde + int((hasta - desde) * rng.random() ** 1.6)
            pasos[paso - 1]["reportes"].append({"zonaId": zona["zonaId"], "tipo": rng.choice(tipos)})
        pasos[inicio - 1]["narrativa"] = f"{guion['titulo']} en {zona['nombre']}"
        pasos[recupera - 1]["narrativa"] = f"Servicio recuperándose en {zona['nombre']}"
    eventos = {z["zonaId"] for z in usadas}
    tranquilas = [z for z in zonas if z["zonaId"] not in eventos]
    for p in pasos[:-4]:
        if tranquilas and rng.random() < _PROB_RUIDO:
            p["reportes"].append({"zonaId": rng.choice(tranquilas)["zonaId"], "tipo": rng.choice(tipos)})
    return pasos


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
