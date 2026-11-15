"""Escenarios de demo (E5).

GET  /api/escenarios          → estado del escenario en curso (o el último)
POST /api/escenarios          → {tipo: TORMENTA | CORTE_ENERGIA, zonaId} lanza la Step Function `escenario`
POST /api/escenarios/reiniciar → "Reiniciar demo": detiene el escenario, quita las fallas forzadas y
                                 marca como restablecidos SOLO los incidentes SIMULADOS abiertos (la SFN de cada uno los
                                 cierra). Los incidentes operativos (reportes reales) no se tocan nunca.
"""
import json
import os
import sys as _sys

import boto3
from boto3.dynamodb.conditions import Attr

from telecorp import config, db, escenarios, historial, http, reglas, util, zonas

_sys.path.insert(0, os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos
import acceso  # noqa: E402

_sfn = boto3.client("stepfunctions")
_lambda = boto3.client("lambda")


def obtener(event, context):
    return http.ok(config.leer("escenario", usar_cache=False))


@acceso.solo_operadores
def lanzar(event, context):
    try:
        cuerpo = http.cuerpo_json(event)
    except ValueError as e:
        return http.error(400, str(e))
    tipo, zona_id = cuerpo.get("tipo"), cuerpo.get("zonaId")
    if tipo not in escenarios.TIPOS:
        return http.error(400, f"tipo debe ser uno de {sorted(escenarios.TIPOS)}")
    if not zonas.zona(zona_id or ""):
        return http.error(400, f"Zona desconocida: {zona_id}")
    if config.leer("escenario", usar_cache=False).get("activo"):
        return http.error(409, "Ya hay un escenario en curso; espera a que termine o reinicia la demo")
    ejecucion = _sfn.start_execution(stateMachineArn=os.environ["MAQUINA_ESCENARIO"],
                                     input=json.dumps({"tipo": tipo, "zonaId": zona_id}))
    return http.respuesta(202, {"ejecucionArn": ejecucion["executionArn"], "tipo": tipo, "zonaId": zona_id})


@acceso.solo_operadores
def reiniciar(event, context):
    estado = config.leer("escenario", usar_cache=False)
    if estado.get("activo") and estado.get("ejecucionArn"):
        try:
            _sfn.stop_execution(executionArn=estado["ejecucionArn"], cause="Reiniciar demo")
        except _sfn.exceptions.ExecutionDoesNotExist:
            pass
    config.escribir("escenario", {**estado, "activo": False, "fin": estado.get("fin") or util.ahora_iso()})

    sim = config.leer("simulador", usar_cache=False)
    sim["fallas"] = {}
    config.escribir("simulador", sim)
    _lambda.invoke(FunctionName=os.environ["FUNCION_SIMULADOR"], InvocationType="Event",
                   Payload=json.dumps({"unaVez": True}).encode())

    abiertos = [c for c in db.scan_todo(db.tabla("colectivos"),
                                        FilterExpression=Attr("estado").is_in(list(reglas.ESTADOS_COLECTIVO_ABIERTOS)))
                if reglas.es_simulado(c)]   # «Reiniciar demo» jamás cierra incidentes de usuarios reales
    actor = f"operador:{acceso.identidad(event)}"   # quién reinició la demo (contrato evento-historial: operador:<sub>)
    for c in abiertos:
        db.tabla("colectivos").update_item(Key={"incidenteColectivoId": c["incidenteColectivoId"]},
                                           UpdateExpression="SET restablecimientoSolicitado = :v", ExpressionAttributeValues={":v": True})
        historial.registrar(c["incidenteColectivoId"], "INCIDENTE_COLECTIVO", "COMENTARIO", actor,
                            detalle="Reinicio de la demo: servicio marcado como restablecido")
    try:  # en Lambda el handler se carga como src.escenarios
        from src.colectivos import reanudar_huerfanos
    except ImportError:  # pruebas locales (pytest añade services/api/src al path)
        from colectivos import reanudar_huerfanos
    reanudados = reanudar_huerfanos()
    return http.ok({"fallasQuitadas": True, "colectivosRestablecidos": len(abiertos), "reanudados": len(reanudados)})
