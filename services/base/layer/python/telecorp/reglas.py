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


# ---------------- Incidencias de usuarios (E2) ----------------
ESTADOS_INCIDENCIA = ("REGISTRADA", "EN_REVISION", "EN_ATENCION", "SOLUCIONADA", "CERRADA")
ESTADOS_INCIDENCIA_ACTIVOS = {"REGISTRADA", "EN_REVISION", "EN_ATENCION"}
TIPOS_PROBLEMA = ("SIN_INTERNET", "INTERNET_LENTO", "SIN_LLAMADAS", "SIN_SMS", "SIN_SENAL", "INTERMITENCIA", "OTRO")


def transicion_valida(actual: str, nuevo: str) -> bool:
    """Solo se avanza en el ciclo de vida (se pueden saltar pasos). Única vuelta atrás: reabrir SOLUCIONADA → EN_ATENCION."""
    if actual not in ESTADOS_INCIDENCIA or nuevo not in ESTADOS_INCIDENCIA:
        return False
    if actual == "SOLUCIONADA" and nuevo == "EN_ATENCION":
        return True
    return ESTADOS_INCIDENCIA.index(nuevo) > ESTADOS_INCIDENCIA.index(actual)


def transiciones_permitidas(actual: str) -> list:
    return [e for e in ESTADOS_INCIDENCIA if transicion_valida(actual, e)]


def validar_reporte(reporte: dict, zonas_validas: set) -> list:
    """Valida un reporte contra contracts/schemas/reporte.schema.json. Devuelve la lista de errores (vacía = válido)."""
    errores = []
    for campo in ("usuarioId", "numeroServicio", "zonaId", "fechaHoraIncidente", "tipo", "descripcion"):
        if not str(reporte.get(campo) or "").strip():
            errores.append(f"Falta el campo obligatorio '{campo}'")
    if reporte.get("zonaId") and reporte["zonaId"] not in zonas_validas:
        errores.append(f"zonaId desconocida: {reporte['zonaId']}")
    if reporte.get("tipo") and reporte["tipo"] not in TIPOS_PROBLEMA:
        errores.append(f"tipo inválido: {reporte['tipo']}")
    if len(str(reporte.get("descripcion") or "")) > 2000:
        errores.append("La descripción supera los 2000 caracteres")
    if not (reporte.get("email") or reporte.get("telefonoContacto")):
        errores.append("Indica un email o un teléfono para poder avisarte")
    ubic = reporte.get("ubicacion")
    if ubic is not None:
        try:
            lat, lng = float(ubic.get("lat")), float(ubic.get("lng"))
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError
        except (TypeError, ValueError, AttributeError):
            errores.append("ubicacion debe tener lat y lng numéricos")
    return errores


# ---------------- Privacidad ----------------
def enmascarar(valor, visibles_inicio: int = 2, visibles_fin: int = 3) -> str:
    """'70123456' → '70***456'. Para mostrar datos personales en el panel sin exponerlos completos."""
    if not valor:
        return valor
    s = str(valor)
    if len(s) <= visibles_inicio + visibles_fin:
        return s[0] + "***"
    return s[:visibles_inicio] + "***" + s[-visibles_fin:]


def enmascarar_email(email):
    if not email or "@" not in email:
        return email
    usuario, dominio = email.split("@", 1)
    return f"{usuario[:1]}***@{dominio}"
