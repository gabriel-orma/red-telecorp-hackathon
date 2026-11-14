"""Pasos de la Step Function `escenario` (E5): tormenta o corte de energía en oleadas.

Estado visible para el panel en SSM /telecorp/<stage>/escenario:
  {activo, tipo, zonaId, oleada, total, inicio, fin, ejecucionArn, reportes, antenas}
"""
import json
import os
import random
import time

import boto3
from botocore.exceptions import ClientError

from telecorp import config, db, escenarios, util, zonas

_sqs = boto3.client("sqs")
_lambda = boto3.client("lambda")
_scheduler = boto3.client("scheduler")
_CAMPOS_SCHEDULE = ("ScheduleExpression", "FlexibleTimeWindow", "Target", "Description",
                    "ScheduleExpressionTimezone", "StartDate", "EndDate", "KmsKeyArn", "GroupName")


def _encender_simulador() -> None:
    """El escenario necesita lecturas en vivo: enciende la programación del simulador si está apagada."""
    nombre = f"telecorp-{os.environ['STAGE']}-simulador"
    actual = _scheduler.get_schedule(Name=nombre)
    if actual["State"] != "ENABLED":
        _scheduler.update_schedule(Name=nombre, State="ENABLED", **{k: actual[k] for k in _CAMPOS_SCHEDULE if k in actual})


def preparar(event, context):
    """{tipo, zonaId, ejecucionArn} → plan de oleadas."""
    plan = escenarios.planificar(event["tipo"], event["zonaId"], zonas.zonas())
    _encender_simulador()
    config.escribir("escenario", {
        "activo": True, "tipo": event["tipo"], "zonaId": event["zonaId"], "oleada": 0, "total": len(plan),
        "inicio": util.ahora_iso(), "fin": None, "ejecucionArn": event.get("ejecucionArn"), "reportes": 0, "antenas": 0,
        "narrativa": None, "acelerada": event["tipo"] == "ACELERADA",
    })
    return {"oleadas": [{**o, "tipo": event["tipo"]} for o in plan]}


def _encolar(reporte: dict) -> bool:
    """Mismo camino que un reporte real: candado de deduplicación + cola SQS (el worker lo registra)."""
    incidencia_id = util.nuevo_id("INC")
    ahora = int(time.time())
    try:
        db.tabla("dedup").put_item(
            Item={"clave": f"{reporte['usuarioId']}#{reporte['zonaId']}", "incidenciaId": incidencia_id, "expiraEn": ahora + 86400},
            ConditionExpression="attribute_not_exists(clave) OR expiraEn < :ahora", ExpressionAttributeValues={":ahora": ahora})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    reporte = {**reporte, "fechaHoraIncidente": util.ahora_iso()}
    _sqs.send_message(QueueUrl=os.environ["COLA_REPORTES_URL"],
                      MessageBody=json.dumps({"incidenciaId": incidencia_id, "creadaEn": util.ahora_iso(), "reporte": reporte}))
    return True


def aplicar_oleada(event, context):
    """Una oleada: fuerza fallas de antenas y envía los reportes de los vecinos."""
    estado = config.leer("escenario", usar_cache=False)
    if not estado.get("activo"):
        return {"omitida": "escenario reiniciado"}

    recuperar = event.get("recuperar") or []
    if event["fallas"] or recuperar:
        sim = config.leer("simulador", usar_cache=False)
        fallas = {**sim.get("fallas", {}), **event["fallas"]}
        for antena_id in recuperar:  # la antena vuelve a su tráfico normal
            fallas.pop(antena_id, None)
        sim["fallas"] = fallas
        config.escribir("simulador", sim)
        _lambda.invoke(FunctionName=f"telecorp-{os.environ['STAGE']}-simulador", InvocationType="Event",
                       Payload=json.dumps({"unaVez": True}).encode())

    rng = random.Random()
    enviados = sum(_encolar(escenarios.reporte_simulado(zonas.zona(r["zonaId"]), r["tipo"], rng)) for r in event["reportes"])
    if event.get("narrativa"):
        estado["narrativa"] = event["narrativa"]
    estado.update(oleada=event["n"], reportes=int(estado.get("reportes", 0)) + enviados,
                  antenas=int(estado.get("antenas", 0)) + len(event["fallas"]))
    config.escribir("escenario", estado)
    return {"oleada": event["n"], "reportes": enviados, "antenas": len(event["fallas"]), "recuperadas": len(recuperar)}


def finalizar(event, context):
    estado = config.leer("escenario", usar_cache=False)
    estado.update(activo=False, fin=util.ahora_iso(), error=(event.get("error") or {}).get("Error"))
    config.escribir("escenario", estado)
    return estado
