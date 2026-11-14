"""Estado en vivo de las nubes conectadas. Alimenta el panel «Nubes conectadas» del centro de control.

GET /api/nubes   (SOLO operadores)  → {aws: {...}, azure: {acsEmail, maps}, ia: {gemini}, generadoEn}

Cada servicio se informa con lo que de verdad se midió, nunca con un valor fijo:
  · AWS   → una operación real y barata por servicio (DynamoDB, SQS, Step Functions) con su latencia.
  · Azure → el tablero que escriben las llamadas reales (envío de correo, clima). Si no hay una llamada reciente se hace
            UNA sonda (ACS: consulta de una operación inexistente, NO envía correo; Maps: clima de una zona), como mucho
            una cada 5 minutos por servicio (cupo atómico), para que abrir el panel no consuma la cuota ni cueste dinero.
  · IA    → solo si hay un modelo configurado; no se llama al modelo desde aquí (cuenta cupo): se informa su último uso real.
Los secretos nunca se devuelven. Ningún fallo de una nube rompe la respuesta: ese servicio se marca `ERROR`.
"""
import os
import sys as _sys
import time

import boto3

from telecorp import db, http, util, zonas
from telecorp.nube2 import azure_acs, azure_maps, estado, ia, secretos

_sys.path.insert(0, os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos
import acceso  # noqa: E402

_sqs = boto3.client("sqs")
_sfn = boto3.client("stepfunctions")
VIGENCIA_TABLERO_S = 900      # una llamada real de hace menos de 15 min basta para decir «operativo»
VIGENCIA_ERROR_S = 60         # un error caduca pronto: se vuelve a comprobar para no mostrar una caída ya resuelta
CUPO_SONDA_S = 300            # como mucho una sonda por servicio cada 5 min
_ESTADOS_OK = ("OK",)


def _medir(funcion) -> dict:
    """Ejecuta una operación real y devuelve {estado, latenciaMs, detalle?}. Nunca lanza."""
    inicio = time.time()
    try:
        funcion()
        return {"estado": "OK", "latenciaMs": int((time.time() - inicio) * 1000), "ultimaLlamada": util.ahora_iso()}
    except Exception as e:  # noqa: BLE001
        return {"estado": "ERROR", "detalle": type(e).__name__, "ultimaLlamada": util.ahora_iso()}


def _aws() -> dict:
    salida = {"dynamodb": _medir(lambda: db.tabla("dedup").get_item(Key={"clave": "NUBE#sonda"}))}
    cola = os.environ.get("COLA_REPORTES_URL")
    salida["sqs"] = (_medir(lambda: _sqs.get_queue_attributes(QueueUrl=cola, AttributeNames=["ApproximateNumberOfMessages"]))
                     if cola else {"estado": "SIN_CONFIGURAR"})
    maquina = os.environ.get("MAQUINA_COLECTIVO")
    salida["stepFunctions"] = (_medir(lambda: _sfn.describe_state_machine(stateMachineArn=maquina))
                               if maquina else {"estado": "SIN_CONFIGURAR"})
    return salida


def _desde_tablero(fila: dict | None, ignorar_vigencia: bool = False) -> dict | None:
    """Convierte una fila del tablero (`NUBE#<servicio>`) al contrato de la interfaz, o None si no hay datos vigentes
    (un OK dura 15 min, un error 60 s; `ignorar_vigencia` devuelve el último dato conocido aunque sea viejo)."""
    if not fila or fila.get("estado") in (None, "SIN_USO"):
        return None
    if fila["estado"] == "NO_CONFIGURADA":
        return {"estado": "SIN_CONFIGURAR"}
    ok = fila["estado"] == "OK"
    if not ignorar_vigencia:
        try:
            edad = (util.ahora() - util.parse_iso(fila["ultimaLlamada"])).total_seconds()
        except Exception:  # noqa: BLE001
            edad = float("inf")
        if edad > (VIGENCIA_TABLERO_S if ok else VIGENCIA_ERROR_S):
            return None
    salida = {"estado": "OK" if ok else "ERROR", "ultimaLlamada": fila.get("ultimaLlamada"), "contador": fila.get("contador", 0)}
    if fila.get("latenciaMs") is not None:
        salida["latenciaMs"] = fila["latenciaMs"]
    if fila.get("ultimoError") and not ok:
        salida["detalle"] = fila["ultimoError"]
    return salida


def _sonda_acs():
    return azure_acs.sondear()


def _sonda_maps():
    z = zonas.zonas()[0]["centro"]
    azure_maps.clima_actual(float(z["lat"]), float(z["lng"]))


def _servicio(clave_tablero: str, configurado: bool, sonda) -> dict:
    if not configurado:
        return {"estado": "SIN_CONFIGURAR"}
    fila = estado.leer_tablero().get(clave_tablero)
    actual = _desde_tablero(fila)
    if actual is not None:
        return actual
    if estado.reservar_cupo(f"sonda-{clave_tablero}", 1, CUPO_SONDA_S):
        sonda()
        fila = estado.leer_tablero().get(clave_tablero)
        actual = _desde_tablero(fila)
        if actual is not None:
            return actual
    # sin cupo (o la sonda no dejó rastro): el último dato conocido, o error si nunca hubo respuesta
    return _desde_tablero(fila, ignorar_vigencia=True) or {"estado": "ERROR", "detalle": "sin respuesta de la nube"}


@acceso.solo_operadores
def obtener(event, context):
    azure = secretos.leer("azure") or {}
    acs_ok = all(azure.get(k) for k in ("acsEndpoint", "acsKey", "acsSender"))
    maps_ok = bool(azure.get("mapsKey"))
    modelo = ia.modelo_configurado()
    gemini = estado.leer_tablero().get("gcp-gemini")
    return http.ok({
        "aws": _aws(),
        "azure": {"acsEmail": _servicio("azure-acs", acs_ok, _sonda_acs),
                  "maps": _servicio("azure-maps", maps_ok, _sonda_maps)},
        "ia": {"gemini": ({"estado": "SIN_CONFIGURAR"} if not modelo else
                          (_desde_tablero(gemini) or {"estado": "OK", "detalle": f"configurada ({modelo}); sin uso reciente"}))},
        "generadoEn": util.ahora_iso(),
    })
