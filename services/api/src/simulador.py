"""Control del simulador de antenas (para pruebas y la demo).

GET /api/simulador → {activo, fallas, ...}
PUT /api/simulador  body: {"activo": true|false, "fallas": {"ANT-013": 0, "ANT-014": null}, "limpiarFallas": true}
  - activo: enciende/apaga la programación de EventBridge Scheduler (apagado = costo 0).
  - fallas: GB/min forzado por antena (null = quitar la falla).
Tras cualquier cambio se dispara una muestra inmediata, para ver el efecto en el mapa sin esperar al minuto siguiente.
"""
import json
import os

import boto3

from telecorp import config, http, zonas

_scheduler = boto3.client("scheduler")
_lambda = boto3.client("lambda")
_CAMPOS_SCHEDULE = ("ScheduleExpression", "FlexibleTimeWindow", "Target", "Description",
                    "ScheduleExpressionTimezone", "StartDate", "EndDate", "KmsKeyArn", "GroupName")


def _schedule():
    return _scheduler.get_schedule(Name=os.environ["PROGRAMACION_SIMULADOR"])


def _estado():
    cfg = config.leer("simulador", usar_cache=False)
    return {"activo": _schedule()["State"] == "ENABLED", **cfg}


def obtener(event, context):
    return http.ok(_estado())


def actualizar(event, context):
    try:
        cuerpo = http.cuerpo_json(event)
    except ValueError as e:
        return http.error(400, str(e))

    cfg = config.leer("simulador", usar_cache=False)
    cambios = False

    if cuerpo.get("limpiarFallas"):
        cfg["fallas"], cambios = {}, True

    validas = {a["antenaId"] for a in zonas.antenas()}
    for antena_id, valor in (cuerpo.get("fallas") or {}).items():
        if antena_id not in validas:
            return http.error(400, f"Antena desconocida: {antena_id}")
        if valor is None:
            cfg["fallas"].pop(antena_id, None)
        else:
            try:
                valor = float(valor)
            except (TypeError, ValueError):
                return http.error(400, f"Valor inválido para {antena_id}: {valor}")
            if valor < 0:
                return http.error(400, "GB/min no puede ser negativo")
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
