"""Reglas de negocio puras (sin AWS). Fuente de verdad: docs/arquitectura.md > Reglas de negocio."""
import math

ESTADOS_ANTENA = ("INHABILITADA", "CAIDA", "NORMAL", "SATURADA")
# Orden de gravedad para resumir una zona por su peor antena (mayor = peor).
GRAVEDAD_ANTENA = {"SIN_DATOS": 0, "NORMAL": 1, "SATURADA": 2, "CAIDA": 3, "INHABILITADA": 4}


def clasificar_antena(gb_por_minuto: float) -> str:
    """0 → INHABILITADA; <60 → CAIDA; 60..129 → NORMAL; >129 → SATURADA.

    Una métrica no física (NaN, ±inf, negativa o booleana) NO se clasifica en silencio: `ValueError`/`TypeError`.
    Las comparaciones usan el valor original (int, float o Decimal) para no perder precisión en las fronteras.
    """
    if isinstance(gb_por_minuto, bool):
        raise TypeError("gbPorMinuto no puede ser booleano")
    numero = float(gb_por_minuto)
    if not math.isfinite(numero) or numero < 0:
        raise ValueError(f"gbPorMinuto inválido (debe ser finito y >= 0): {gb_por_minuto!r}")
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
def enmascarar(valor, visibles_inicio: int = 2, visibles_fin: int = 2) -> str:
    """'70123456' → '70***56'. Deja visibles ≤ 4 de 8 dígitos (con 5 visibles quedaban solo 1.000 combinaciones por fuerza bruta)."""
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


# Reporte de texto libre (`OTRO`) clasificado por la IA: "la IA solo suma". Un OTRO cuenta para disparar un colectivo
# únicamente si la IA REAL lo clasificó como problema del servicio con confianza suficiente y un tipo del catálogo; si la IA
# falla, no responde o duda, sigue sin contar (como antes). La IA nunca resta reportes que las reglas ya cuentan.
UMBRAL_CONFIANZA_TRIAGE_IA = 0.8       # IA generativa (Gemini): cuando se activa el triage de texto
UMBRAL_CONFIANZA_TRIAGE_ML = 0.5       # modelo local (TF-IDF + regresión logística): se fija con la validación cruzada del entrenamiento
                                       # (ml/triage/resultados.json); una prueba comprueba que coincide con el que guarda el modelo
_UMBRAL_TRIAGE = {"IA": UMBRAL_CONFIANZA_TRIAGE_IA, "ML": UMBRAL_CONFIANZA_TRIAGE_ML}


def triage_ia_confirma_servicio(triage) -> bool:
    """¿Un reporte OTRO clasificado automáticamente cuenta como problema del servicio? Solo si lo clasificó un MODELO real (IA
    generativa o ML local; nunca las reglas) con confianza suficiente y un tipo del catálogo."""
    try:
        umbral = _UMBRAL_TRIAGE.get(triage.get("fuente")) if isinstance(triage, dict) else None
        return (umbral is not None and triage.get("relacionado") is True and float(triage.get("confianza", 0)) >= umbral
                and triage.get("tipoSugerido") in TIPOS_PROBLEMA and triage.get("tipoSugerido") != "OTRO")
    except (TypeError, ValueError):
        return False


def es_colectivo(usuarios_distintos: int, umbral: int = 10) -> bool:
    """≥ umbral usuarios distintos (la ventana de <24 h la aplica la consulta)."""
    return usuarios_distintos >= umbral


def entra_en_falla(estado_anterior, estado_nuevo) -> bool:
    return estado_nuevo in ESTADOS_ANTENA_FALLA and estado_anterior not in ESTADOS_ANTENA_FALLA


def calcular_prioridad(afectados: int, criticidad: int, antenas_en_falla: int, cfg: dict, horas_activo: float = 0) -> tuple:
    """(puntaje, prioridad). TODO(D7): fórmula y pesos provisionales; se ajustan en SSM sin tocar código.

    puntaje = (afectados × pesoAfectado + antenasEnFalla × pesoAntenaEnFalla) × criticidad × (1 + horasActivo × pesoHora)
    El factor de tiempo hace que un incidente que lleva horas sin resolverse suba en la cola de atención.
    """
    base = (afectados * cfg.get("pesoAfectado", 1) + antenas_en_falla * cfg.get("pesoAntenaEnFalla", 10)) * criticidad
    puntaje = base * (1 + max(0.0, horas_activo) * cfg.get("pesoHora", 0.25))
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
        # Privacidad: ≈ 110 m bastan para ubicar la zona; el cliente ya la redondea y el servidor lo garantiza aunque no lo haga.
        reporte["ubicacion"] = {"lat": round(float(ubic["lat"]), 3), "lng": round(float(ubic["lng"]), 3)}
    return {k: v for k, v in reporte.items() if v is not None}


# ---------------- Inteligencia operativa (E6) ----------------
def deteccion_anticipada_min(primera_falla_iso, primer_reporte_iso):
    """Minutos entre la primera falla de antena y el primer reporte de usuario.
    Positivo: la red lo detectó antes que los usuarios. None si falta alguno de los dos."""
    if not primera_falla_iso or not primer_reporte_iso:
        return None
    from datetime import datetime
    a = datetime.fromisoformat(primera_falla_iso.replace("Z", "+00:00"))
    b = datetime.fromisoformat(primer_reporte_iso.replace("Z", "+00:00"))
    return round((b - a).total_seconds() / 60, 1)


def es_simulado(entidad: dict | None) -> bool:
    """¿El dato nace de una simulación (escenario de demo, fallas forzadas del simulador, vecinos ficticios)?

    Vale para incidencias (`reporte.simulado`), colectivos, antenas (`simulada`) y eventos de historial (`simulado`).
    Es la ÚNICA definición: detector, estadísticas, analítica y recurrencia la comparten, así lo simulado nunca se mezcla
    con lo operativo (ni lo infla ni lo oculta). El usuario no puede enviarla: `construir_reporte` no la admite."""
    e = entidad or {}
    return bool(e.get("simulado") or e.get("simulada") or (e.get("reporte") or {}).get("simulado"))


def contar_fallas(eventos: list, desde_iso: str, simulados: bool = False) -> int:
    """Veces que una antena ENTRÓ en falla (caída o inhabilitada) desde `desde_iso`, según su historial.

    Solo cuenta un universo de datos: los operativos (por defecto) o los simulados (`simulados=True`)."""
    return sum(1 for e in eventos
               if e.get("tipoEvento") == "CAMBIO_ESTADO" and e.get("ocurridoEn", "") >= desde_iso
               and es_simulado(e) == simulados
               and entra_en_falla(e.get("estadoAnterior"), e.get("estadoNuevo")))


def es_estructural(fallas: int, cfg: dict) -> bool:
    """TODO(D7): umbral provisional (3 fallas en 7 días), configurable en SSM."""
    return fallas >= cfg.get("umbralFallas", 3)
