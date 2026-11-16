"""Control del simulador de antenas (para pruebas y la demo).

GET /api/simulador → {activo, fallas, ...}
PUT /api/simulador  body: {"activo": true|false, "fallas": {"ANT-013": 0, "ANT-014": null}, "limpiarFallas": true}
  - activo: enciende/apaga la programación de EventBridge Scheduler (apagado = costo 0).
  - fallas: GB/min forzado por antena (null = quitar la falla).
Tras cualquier cambio se dispara una muestra inmediata, para ver el efecto en el mapa sin esperar al minuto siguiente.

Ambas rutas son SOLO DE OPERADOR (autorizador JWT + grupo `operadores`, ver `acceso.py`): el simulador cuesta dinero al
estar encendido y puede inyectar métricas falsas. La entrada se valida COMPLETA antes de leer o escribir nada: un valor
`nan`/`inf`/fuera de rango se rechaza con 400 en lugar de guardarse como métrica "veneno".
"""
import json
import math
import os
import sys as _sys

_sys.path.insert(0, os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos

import boto3

from telecorp import config, http, zonas
import acceso  # noqa: E402
import incidentes_reales  # noqa: E402

_scheduler = boto3.client("scheduler")
_lambda = boto3.client("lambda")
_CAMPOS_SCHEDULE = ("ScheduleExpression", "FlexibleTimeWindow", "Target", "Description",
                    "ScheduleExpressionTimezone", "StartDate", "EndDate", "KmsKeyArn", "GroupName")
GB_MAXIMO = 1000.0  # techo de una falla forzada: muy por encima de la zona "saturada" (>129) y de cualquier valor real


def _validar(cuerpo: dict):
    """Valida el cuerpo completo. Devuelve ({antenaId: float | None}, None) o (None, mensaje de error 400)."""
    if "activo" in cuerpo and not isinstance(cuerpo["activo"], bool):
        return None, "activo debe ser true o false"
    fallas = cuerpo.get("fallas")
    if fallas is None:
        return {}, None
    if not isinstance(fallas, dict):
        return None, "fallas debe ser un objeto {antenaId: GB/min | null}"
    validas = {a["antenaId"] for a in zonas.antenas()}
    limpias = {}
    for antena_id, valor in fallas.items():
        if antena_id not in validas:
            return None, f"Antena desconocida: {antena_id}"
        if valor is None:
            limpias[antena_id] = None
            continue
        if isinstance(valor, bool):
            return None, f"Valor inválido para {antena_id}: {valor}"
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return None, f"Valor inválido para {antena_id}: {valor}"
        if not math.isfinite(numero):
            return None, f"Valor inválido para {antena_id}: debe ser un número finito"
        if numero < 0:
            return None, "GB/min no puede ser negativo"
        if numero > GB_MAXIMO:
            return None, f"GB/min no puede superar {GB_MAXIMO:g}"
        limpias[antena_id] = numero
    return limpias, None


def _schedule():
    return _scheduler.get_schedule(Name=os.environ["PROGRAMACION_SIMULADOR"])


def _estado():
    cfg = config.leer("simulador", usar_cache=False)
    return {"activo": _schedule()["State"] == "ENABLED", **cfg}


@acceso.solo_operadores
def obtener(event, context):
    return http.ok(_estado())


@acceso.solo_operadores
def actualizar(event, context):
    try:
        cuerpo = http.cuerpo_json(event)
    except ValueError as e:
        return http.error(400, str(e))
    fallas, error = _validar(cuerpo)  # se valida TODO antes de tocar SSM o el scheduler
    if error:
        return http.error(400, error)
    # Forzar una falla cambia el estado compartido de la antena: no se permite sobre una zona con un incidente real abierto.
    forzadas = [a for a, v in fallas.items() if v is not None]
    if forzadas:
        reales = incidentes_reales.abiertos_en(incidentes_reales.zonas_de_antenas(forzadas))
        if reales:
            return http.error(409, incidentes_reales.mensaje(reales))

    cfg = config.leer("simulador", usar_cache=False)
    cambios = False

    if cuerpo.get("limpiarFallas"):
        cfg["fallas"], cambios = {}, True

    for antena_id, valor in fallas.items():
        if valor is None:
            cfg["fallas"].pop(antena_id, None)
        else:
            cfg["fallas"][antena_id] = valor
        cambios = True

    if cambios:
        config.escribir("simulador", cfg)

    if "activo" in cuerpo:
        actual = _schedule()
        nuevo = "ENABLED" if cuerpo["activo"] else "DISABLED"
        if actual["State"] != nuevo:
            _scheduler.update_schedule(
                Name=actual["Name"], State=nuevo,
                **{k: actual[k] for k in _CAMPOS_SCHEDULE if k in actual},
            )
            cambios = cambios or nuevo == "ENABLED"

    if cambios:
        _lambda.invoke(FunctionName=os.environ["FUNCION_SIMULADOR"], InvocationType="Event",
                       Payload=json.dumps({"unaVez": True}).encode())

    return http.ok(_estado())
