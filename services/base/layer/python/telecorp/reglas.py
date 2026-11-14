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


# ---------------- Incidentes colectivos (E3) ----------------
ESTADOS_COLECTIVO_ABIERTOS = {"EN_EVALUACION", "INCIDENCIA_CONFIRMADA"}
ESTADOS_ANTENA_FALLA = {"INHABILITADA", "CAIDA"}  # disparan detección proactiva
# La VERIFICACIÓN de un colectivo (H24) también considera SATURADA: con 10 usuarios reportando "Internet lento" una antena
# saturada ES la causa. No dispara detección proactiva (una saturación pasajera no justifica abrir un incidente).
ESTADOS_ANTENA_VERIFICACION = ESTADOS_ANTENA_FALLA | {"SATURADA"}


def es_colectivo(usuarios_distintos: int, umbral: int = 10) -> bool:
    """≥ umbral usuarios distintos (la ventana de <24 h la aplica la consulta)."""
    return usuarios_distintos >= umbral


def entra_en_falla(estado_anterior, estado_nuevo) -> bool:
    return estado_nuevo in ESTADOS_ANTENA_FALLA and estado_anterior not in ESTADOS_ANTENA_FALLA


def calcular_prioridad(afectados: int, criticidad: int, antenas_en_falla: int, cfg: dict) -> tuple:
    """(puntaje, prioridad). TODO(D7): fórmula y pesos provisionales; se ajustan en SSM sin tocar código.

    puntaje = (afectados × pesoAfectado + antenasEnFalla × pesoAntenaEnFalla) × criticidad de la zona
    """
    puntaje = (afectados * cfg.get("pesoAfectado", 1) + antenas_en_falla * cfg.get("pesoAntenaEnFalla", 10)) * criticidad
    umbrales = cfg.get("umbrales", {"MEDIA": 20, "ALTA": 50, "CRITICA": 100})
    prioridad = "BAJA"
    for nivel in ("MEDIA", "ALTA", "CRITICA"):
        if puntaje >= umbrales[nivel]:
            prioridad = nivel
    return round(puntaje, 1), prioridad


# ---------------- Reporte mínimo con cuenta (E3.5) ----------------
def perfil_desde_claims(claims: dict) -> dict:
    """Atributos del ID token de Cognito → perfil (contracts/schemas/usuario.schema.json)."""
    return {
        "email": claims.get("email"), "nombre": claims.get("name"), "dni": claims.get("custom:dni"),
        "numeroServicio": claims.get("custom:numeroServicio"), "telefono": claims.get("phone_number"),
        "zonaId": claims.get("custom:zonaId"), "avisosEmail": claims.get("custom:avisosEmail", "0"),
    }


def construir_reporte(cuerpo: dict, perfil: dict, zona_gps: str | None, ahora_iso: str) -> dict:
    """El usuario solo manda {tipo, descripcion, ubicacion?}: el resto sale de su cuenta.

    Zona: la del GPS si cae en cobertura; si no hay GPS (o está fuera), la zona del servicio de la cuenta.
    """
    ubic = cuerpo.get("ubicacion") if zona_gps else None
    reporte = {
        "usuarioId": perfil.get("dni"), "nombre": perfil.get("nombre"),
        "numeroServicio": perfil.get("numeroServicio"), "email": perfil.get("email"),
        "telefonoContacto": perfil.get("telefono"),
        "zonaId": zona_gps or perfil.get("zonaId"),
        "ubicacionFuente": "GPS" if zona_gps else "CUENTA",
        "fechaHoraIncidente": cuerpo.get("fechaHoraIncidente") or ahora_iso,
        "tipo": cuerpo.get("tipo"), "descripcion": str(cuerpo.get("descripcion") or "").strip(),
        "avisarPorEmail": perfil.get("avisosEmail") == "1",
    }
    if ubic:
        reporte["ubicacion"] = {"lat": float(ubic["lat"]), "lng": float(ubic["lng"])}
    return {k: v for k, v in reporte.items() if v is not None}
