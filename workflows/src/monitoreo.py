"""Reglas PURAS del monitoreo de un incidente colectivo (sin AWS: se prueban con casos límite).

La Step Function consulta, en cada vuelta, qué hacer con el colectivo. Esta función es la única que decide:

1. **Operador**: si pidió el restablecimiento → restablecido (vía OPERADOR).
2. **Con antenas registradas** (el colectivo tuvo antenas en falla/saturadas): se restablece cuando TODAS ya no están
   degradadas (vía AUTOMATICO).
3. **Sin antenas registradas** (nació solo de reportes y la red está normal): no hay antena que "se recupere", así que se
   cierra por **silencio**: ningún reporte nuevo en la zona durante `cierreSinReportesMinutos` (vía SIN_REPORTES).
   Sin esta regla el colectivo nunca terminaba (defecto C5/H03 de la auditoría).
4. Si hay una antena degradada y el colectivo aún no estaba confirmado → `escalar` (se confirma y se avisa; así NUNCA se
   dice "falla confirmada" cuando la red estaba bien, y si la falla aparece después, sí se avisa).
5. **Acotado**: `agotado` por iteraciones (protege el límite de 25.000 eventos de historial de Step Functions) o por
   tiempo máximo de monitoreo → atención manual.
"""
from telecorp import reglas


def cantidad_lotes(total: int, tam: int) -> int:
    """Cuántos lotes de `tam` hacen falta para `total` destinatarios (0 si no hay)."""
    return 0 if total <= 0 else -(-total // max(1, tam))


def decidir(*, solicitado: bool, afectadas: list, estados: dict, confirmada: bool, sin_reportes_recientes: bool,
            iteracion: int, max_iteraciones: int, minutos_transcurridos: float, max_minutos: float) -> dict:
    """Resultado de la verificación: {restablecido, via, agotado, escalar}.

    `afectadas`: antenaId registradas en el colectivo. `estados`: estado actual de las antenas de la zona.
    `sin_reportes_recientes`: no entró ningún reporte en la zona dentro de la ventana de silencio.
    """
    if solicitado:
        return {"restablecido": True, "via": "OPERADOR", "agotado": False, "escalar": False}
    degradadas_ahora = any(e in reglas.ESTADOS_ANTENA_VERIFICACION for e in estados.values())
    if afectadas:
        if all(estados.get(a) not in reglas.ESTADOS_ANTENA_VERIFICACION for a in afectadas):
            return {"restablecido": True, "via": "AUTOMATICO", "agotado": False, "escalar": False}
    elif not degradadas_ahora and sin_reportes_recientes:
        return {"restablecido": True, "via": "SIN_REPORTES", "agotado": False, "escalar": False}
    agotado = iteracion >= max_iteraciones or minutos_transcurridos >= max_minutos
    return {"restablecido": False, "agotado": agotado, "escalar": degradadas_ahora and not confirmada}
