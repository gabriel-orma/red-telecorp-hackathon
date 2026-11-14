"""Incidencias de usuarios (E2).

POST  /api/reportes                    → valida, deduplica y encola en SQS (202). El worker la registra.
SQS   reportes → registrar             → put idempotente (condicional) + historial CREADO.
GET   /api/incidencias                 → lista PÚBLICA (filtros: zonaId, estado, horas, limite). Solo lista blanca.
GET   /api/incidencias/{id}            → detalle PÚBLICO + historial + transiciones + estado de la zona. Solo lista blanca.
GET   /api/operador/incidencias[/{id}] → lo mismo con el detalle del reporte (nombre, ubicación, descripción). Solo operadores.
PATCH /api/incidencias/{id}/estado     → cambio de estado validado + historial. Solo operadores.

Privacidad (R3): sin sesión se devuelve únicamente una LISTA BLANCA de campos (estado, tipo, zona, fechas). Nombre, GPS
exacto, descripción libre y datos de contacto solo los ve un operador autenticado (ID token + grupo `operadores`, ver
`acceso.py`); aun así el DNI, el servicio, el correo y el teléfono se muestran enmascarados.
"""
import json
import math
import os
import sys as _sys
import time
from datetime import datetime, timedelta, timezone

_sys.path.insert(0, os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from telecorp import db, estadisticas, historial, http, notificador, reglas, util, zonas
from telecorp.nube2 import ia
import acceso  # noqa: E402

_sqs = boto3.client("sqs")
VENTANA_DEDUP_HORAS = 24
FECHA_INCIDENTE_MAX_ANTIGUEDAD = timedelta(days=7)
FECHA_INCIDENTE_MAX_ADELANTO = timedelta(minutes=5)

# Lista blanca de la vista pública: nada de nombre, GPS, descripción libre, contacto ni identificadores de la persona.
_CAMPOS_PUBLICOS = ("incidenciaId", "estado", "creadaEn", "actualizadaEn", "zonaId", "tipo", "incidenteColectivoId")
_CAMPOS_REPORTE_PUBLICOS = ("tipo", "zonaId", "fechaHoraIncidente", "ubicacionFuente")

# H19. Al recibir el reporte solo se RESERVA la clave de deduplicación el tiempo que SQS puede tardar en entregar el
# mensaje al worker (visibilidad 180 s × maxReceiveCount 5 = 15 min). El worker la extiende a 24 h al registrar la
# incidencia. Si el mensaje se agota y cae a la DLQ, la reserva caduca sola y el usuario puede volver a reportar.
RESERVA_DEDUP_SEGUNDOS = 20 * 60


# ---------------- Utilidades ----------------
def _vista_publica(item: dict) -> dict:
    """Vista sin sesión: SOLO los campos de la lista blanca (H02)."""
    rep = item.get("reporte", {})
    salida = {k: item[k] for k in _CAMPOS_PUBLICOS if k in item}
    salida["reporte"] = {k: rep[k] for k in _CAMPOS_REPORTE_PUBLICOS if k in rep}
    salida["transicionesPermitidas"] = reglas.transiciones_permitidas(item["estado"])
    return salida


def _vista_operador(item: dict, completa: bool = False) -> dict:
    """Vista de operador autenticado: ve el detalle del reporte, pero identificadores y contacto salen enmascarados."""
    rep = dict(item.get("reporte", {}))
    rep["usuarioId"] = reglas.enmascarar(rep.get("usuarioId"))
    rep["numeroServicio"] = reglas.enmascarar(rep.get("numeroServicio"))
    rep["email"] = reglas.enmascarar_email(rep.get("email"))
    rep["telefonoContacto"] = reglas.enmascarar(rep.get("telefonoContacto"), 4, 3)
    if not completa:
        rep["descripcion"] = (rep.get("descripcion") or "")[:160]
    salida = {**item, "reporte": rep, "usuarioId": rep["usuarioId"]}
    salida["transicionesPermitidas"] = reglas.transiciones_permitidas(item["estado"])
    return salida


def _vista(item: dict, operador: bool, completa: bool = False) -> dict:
    return _vista_operador(item, completa) if operador else _vista_publica(item)


def _fecha_incidente(valor):
    """Valida `fechaHoraIncidente` (H26): texto ISO-8601 con zona horaria, ≤ 40 caracteres y dentro de
    [ahora − 7 días, ahora + 5 min]. Devuelve (iso_utc, None) o (None, mensaje)."""
    if not isinstance(valor, str) or len(valor) > 40:
        return None, "fechaHoraIncidente debe ser un texto ISO-8601 (p. ej. 2026-11-14T10:30:00-05:00)"
    try:
        t = datetime.fromisoformat(valor)
    except ValueError:
        return None, "fechaHoraIncidente no es una fecha ISO-8601 válida"
    if t.tzinfo is None:
        return None, "fechaHoraIncidente debe incluir la zona horaria (Z o ±hh:mm)"
    t = t.astimezone(timezone.utc)
    ahora = datetime.now(timezone.utc)
    if not (ahora - FECHA_INCIDENTE_MAX_ANTIGUEDAD <= t <= ahora + FECHA_INCIDENTE_MAX_ADELANTO):
        return None, "fechaHoraIncidente está fuera del rango permitido (últimos 7 días)"
    return t.isoformat(timespec="milliseconds").replace("+00:00", "Z"), None


def _incidencias_zona(zona_id: str, desde_iso: str) -> list:
    t, items, kwargs = db.tabla("incidencias"), [], {}
    while True:
        r = t.query(IndexName="zona-fecha",
                    KeyConditionExpression=Key("zonaId").eq(zona_id) & Key("creadaEn").gte(desde_iso),
                    ScanIndexForward=False, **kwargs)
        items.extend(r["Items"])
        if "LastEvaluatedKey" not in r:
            return items
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def _historial(entidad_id: str, operador: bool = False) -> list:
    r = db.tabla("historial").query(KeyConditionExpression=Key("entidadId").eq(entidad_id))
    eventos = [{k: v for k, v in e.items() if k != "sk"} for e in r["Items"]]
    if not operador:  # el público no debe ver el `sub` de quien operó: solo que fue un operador
        for e in eventos:
            if str(e.get("actor", "")).startswith("operador:"):
                e["actor"] = "OPERADOR"
    return eventos


# ---------------- Endpoints ----------------
def crear_reporte(event, context):
    """POST /api/reportes (requiere sesión). Cuerpo mínimo: {tipo, descripcion, ubicacion?}.

    Los datos personales salen del ID token de Cognito (validado por el autorizador JWT del HTTP API). La identidad
    del reporte (`usuarioId`) es el `sub` del token, nunca `custom:dni`: el usuario puede editar su DNI, no su `sub`.
    """
    try:
        cuerpo = http.cuerpo_json(event)
    except ValueError as e:
        return http.error(400, str(e))
    sub = acceso.identidad(event)
    if sub is None:
        return http.error(401, "Inicia sesión para reportar")
    if not acceso.id_valido(sub):
        return http.error(400, "Identificador de usuario inválido")
    perfil = reglas.perfil_desde_claims(acceso.claims_de(event))

    fecha_incidente = None
    if cuerpo.get("fechaHoraIncidente") is not None:
        fecha_incidente, error_fecha = _fecha_incidente(cuerpo["fechaHoraIncidente"])
        if error_fecha:
            return http.error(400, error_fecha)

    zona_gps = None
    ubic = cuerpo.get("ubicacion")
    if isinstance(ubic, dict):
        try:
            lat, lng = float(ubic["lat"]), float(ubic["lng"])
        except (KeyError, TypeError, ValueError):
            return http.error(400, "ubicacion debe tener lat y lng numéricos")
        if not (math.isfinite(lat) and math.isfinite(lng) and -90 <= lat <= 90 and -180 <= lng <= 180):
            return http.error(400, "ubicacion fuera de rango")
        z = zonas.ubicar(lat, lng)
        zona_gps = z["zonaId"] if z else None
    reporte = reglas.construir_reporte(cuerpo, perfil, zona_gps, util.ahora_iso())
    reporte["usuarioId"] = sub
    if fecha_incidente:
        reporte["fechaHoraIncidente"] = fecha_incidente

    errores = reglas.validar_reporte(reporte, {z["zonaId"] for z in zonas.zonas()})
    if errores:
        return http.error(400, "El reporte tiene errores", errores=errores)

    # Deduplicación atómica (clave condicional): un usuario con un reporte activo en la zona no genera otro,
    # así no cuenta dos veces para la regla de 10 usuarios. Es consistente aunque el worker aún no haya corrido.
    incidencia_id = util.nuevo_id("INC")
    clave = _clave_dedup(reporte["usuarioId"], reporte["zonaId"])
    ahora = int(time.time())
    try:
        db.tabla("dedup").put_item(
            Item={"clave": clave, "incidenciaId": incidencia_id, "expiraEn": ahora + RESERVA_DEDUP_SEGUNDOS,
                  "estado": "RESERVADO"},
            ConditionExpression="attribute_not_exists(clave) OR expiraEn < :ahora",
            ExpressionAttributeValues={":ahora": ahora},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        previa = db.tabla("dedup").get_item(Key={"clave": clave}, ConsistentRead=True).get("Item", {})
        return http.ok({"incidenciaId": previa.get("incidenciaId"), "duplicado": True,
                        "mensaje": "Ya tienes un reporte activo en esta zona; te mostramos su seguimiento."})

    # Avisos por correo (opt-in): SNS envía al usuario un correo para confirmar la suscripción.
    suscripcion = None
    if reporte.get("avisarPorEmail") and reporte.get("email"):
        try:
            suscripcion = "pendiente" if notificador.suscribir_email(reporte["email"], reporte["usuarioId"]) else None
        except Exception as e:  # noqa: BLE001 - el reporte no debe fallar por el canal de email
            print(f"No se pudo suscribir el email: {e!r}")

    mensaje = {"incidenciaId": incidencia_id, "creadaEn": util.ahora_iso(), "reporte": reporte}
    try:
        _sqs.send_message(QueueUrl=os.environ["COLA_REPORTES_URL"], MessageBody=json.dumps(mensaje))
    except Exception:
        db.tabla("dedup").delete_item(Key={"clave": clave})  # no bloquear al usuario si no se encoló
        raise
    return http.respuesta(202, {"incidenciaId": incidencia_id, "estado": "REGISTRADA", "duplicado": False,
                                "avisoEmail": suscripcion, "zonaId": reporte["zonaId"],
                                "ubicacionFuente": reporte["ubicacionFuente"]})


def _clave_dedup(usuario_id: str, zona_id: str) -> str:
    return db.clave_dedup_usuario(usuario_id, zona_id)


def _registrar_incidencia(m: dict, triage: dict | None = None) -> None:
    """Crea la incidencia, su historial CREADO y los contadores del estado público en UNA transacción (H17): o quedan
    los tres o ninguno, así un reintento de SQS nunca encuentra una incidencia "a medias". Idempotente: si la
    incidencia ya existe, la transacción se cancela y el reintento no duplica nada."""
    rep = m["reporte"]
    item = {
        "incidenciaId": m["incidenciaId"], "estado": "REGISTRADA",
        "creadaEn": m["creadaEn"], "actualizadaEn": m["creadaEn"],
        "zonaId": rep["zonaId"], "usuarioId": rep["usuarioId"], "tipo": rep["tipo"],
        "reporte": rep,
    }
    if triage:
        item["iaTriage"] = triage   # solo la escribe el worker (servidor): el usuario no puede enviarla. La vista pública NO la expone.
    b, ttl = estadisticas.bucket_de_iso(m["creadaEn"]), int(time.time()) + estadisticas.TTL_DIAS * 86400
    operaciones = [
        ("Put", "incidencias", {"Item": util.a_dynamo(item), "ConditionExpression": "attribute_not_exists(incidenciaId)"}),
        ("Put", "historial", {"Item": historial.evento(
            m["incidenciaId"], "INCIDENCIA", "CREADO", "USUARIO",
            detalle=f"Zona {(zonas.zona(rep['zonaId']) or {}).get('nombre', rep['zonaId'])}",
            estado_nuevo="REGISTRADA", ocurrido_en=m["creadaEn"], token="creado")}),
    ]
    # Contadores para la página pública de estado (serie global y de la zona).
    for serie in ("GLOBAL", rep["zonaId"]):
        operaciones.append(("Update", "estadisticas", estadisticas.argumentos_incremento(serie, b, rep["tipo"], ttl)))
    try:
        db.transaccion(operaciones)
    except ClientError as e:
        if db.es_transaccion_cancelada(e) and db.motivos_cancelacion(e)[:1] == ["ConditionalCheckFailed"]:
            return  # ya registrada en un intento anterior
        raise


def _confirmar_dedup(rep: dict, incidencia_id: str) -> None:
    """La reserva pasa a ser el bloqueo de 24 h de "un reporte activo por usuario y zona" (mejor esfuerzo)."""
    try:
        db.tabla("dedup").update_item(
            Key={"clave": _clave_dedup(rep["usuarioId"], rep["zonaId"])},
            UpdateExpression="SET expiraEn = :x, estado = :a", ConditionExpression="incidenciaId = :i",
            ExpressionAttributeValues={":x": int(time.time()) + VENTANA_DEDUP_HORAS * 3600, ":a": "ACTIVO",
                                       ":i": incidencia_id})
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise  # si la reserva ya caducó o es de otro reporte, no hay nada que extender


# Segundos de Lambda que deben quedar libres después de consultar a la IA (el worker procesa hasta 10 reportes por lote).
MARGEN_TRIAGE_SEGUNDOS = 10.0
CAMPOS_TRIAGE = ("relacionado", "tipoSugerido", "urgencia", "confianza", "fuente", "modelo", "motivo")


def _triage_ia(rep: dict, context) -> dict | None:
    """Triage por IA del texto libre de un reporte `OTRO` (los demás tipos ya cuentan por reglas y no gastan tokens).
    Mejor esfuerzo y con plazo corto: ante cualquier problema el reporte se registra igual, sin `iaTriage`."""
    if rep.get("tipo") != "OTRO":
        return None
    try:
        restante = context.get_remaining_time_in_millis() / 1000 if hasattr(context, "get_remaining_time_in_millis") else 30.0
        if restante < MARGEN_TRIAGE_SEGUNDOS + 2:
            return None
        r = ia.triage_reporte(rep.get("descripcion"), "OTRO", plazo_s=min(4.0, restante - MARGEN_TRIAGE_SEGUNDOS))
        return {k: r[k] for k in CAMPOS_TRIAGE if k in r}
    except Exception as e:  # noqa: BLE001
        print(f"triage IA omitido ({type(e).__name__})")
        return None


def registrar(event, context):
    """Worker SQS: crea la incidencia de forma idempotente y atómica (los reintentos de SQS no duplican ni pierden)."""
    fallidos = []
    for r in event.get("Records", []):
        try:
            m = json.loads(r["body"])
            _registrar_incidencia(m, _triage_ia(m["reporte"], context))
            _confirmar_dedup(m["reporte"], m["incidenciaId"])
        except Exception as e:  # noqa: BLE001 - vuelve a la cola; tras 5 intentos, a la DLQ (con alarma)
            print(f"ERROR reporte {r.get('messageId')}: {e!r}")
            fallidos.append({"itemIdentifier": r["messageId"]})
    return {"batchItemFailures": fallidos}


def _liberar_dedup(item: dict) -> None:
    try:
        db.tabla("dedup").delete_item(
            Key={"clave": _clave_dedup(item["usuarioId"], item["zonaId"])},
            ConditionExpression="incidenciaId = :i", ExpressionAttributeValues={":i": item["incidenciaId"]},
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def mis_reportes(event, context):
    """GET /api/mis-reportes (requiere sesión): los reportes del usuario, sin enmascarar porque son suyos."""
    claims = acceso.claims_de(event)
    sub = acceso.identidad(event)
    if not acceso.id_valido(sub):
        return http.error(401, "Inicia sesión")
    r = db.tabla("incidencias").query(IndexName="usuario-fecha", KeyConditionExpression=Key("usuarioId").eq(sub),
                                      ScanIndexForward=False, Limit=50)
    salida = []
    for i in r["Items"]:
        salida.append({k: i.get(k) for k in ("incidenciaId", "estado", "creadaEn", "actualizadaEn", "zonaId", "tipo",
                                             "incidenteColectivoId")}
                      | {"descripcion": i["reporte"].get("descripcion"), "ubicacionFuente": i["reporte"].get("ubicacionFuente"),
                         "zona": (zonas.zona(i["zonaId"]) or {}).get("nombre")})
    return http.ok({"reportes": salida, "perfil": reglas.perfil_desde_claims(claims)})


def listar(event, context):
    """GET /api/incidencias (pública): solo lista blanca."""
    return _listar(event, operador=False)


@acceso.solo_operadores
def listar_operador(event, context):
    """GET /api/operador/incidencias (JWT + grupo `operadores`): con el detalle del reporte."""
    return _listar(event, operador=True)


def _listar(event, operador: bool):
    q = event.get("queryStringParameters") or {}
    try:
        horas = min(max(int(q.get("horas", 72)), 1), 24 * 30)
        limite = min(max(int(q.get("limite", 200)), 1), 1000)
    except ValueError:
        return http.error(400, "horas y limite deben ser enteros")
    desde = util.hace_iso(hours=horas)
    if q.get("zonaId"):
        items = _incidencias_zona(q["zonaId"], desde)
    else:
        items = db.scan_todo(db.tabla("incidencias"), FilterExpression=Attr("creadaEn").gte(desde))
    if q.get("estado"):
        items = [i for i in items if i["estado"] == q["estado"]]
    items.sort(key=lambda i: i["creadaEn"], reverse=True)
    return http.ok({"incidencias": [_vista(i, operador) for i in items[:limite]], "total": len(items)})


def obtener(event, context):
    """GET /api/incidencias/{id} (pública): solo lista blanca."""
    return _obtener(event, operador=False)


@acceso.solo_operadores
def obtener_operador(event, context):
    """GET /api/operador/incidencias/{id} (JWT + grupo `operadores`): con el detalle del reporte."""
    return _obtener(event, operador=True)


def _obtener(event, operador: bool):
    incidencia_id = event["pathParameters"]["incidenciaId"]
    item = db.tabla("incidencias").get_item(Key={"incidenciaId": incidencia_id}).get("Item")
    if not item:
        return http.error(404, "Incidencia no encontrada (si la acabas de crear, se está registrando)")

    zona = zonas.zona(item["zonaId"]) or {}
    activas = [i for i in _incidencias_zona(item["zonaId"], util.hace_iso(hours=24))
               if i.get("estado") in reglas.ESTADOS_INCIDENCIA_ACTIVOS]
    antenas = db.tabla("antenas")
    estados_antenas = [antenas.get_item(Key={"antenaId": a["antenaId"]}).get("Item", {}).get("estado", "SIN_DATOS")
                       for a in zona.get("antenas", [])]
    colectivo = None
    if item.get("incidenteColectivoId"):
        c = db.tabla("colectivos").get_item(Key={"incidenteColectivoId": item["incidenteColectivoId"]}).get("Item")
        if c:
            colectivo = {k: c.get(k) for k in ("incidenteColectivoId", "estado", "pasoActual", "prioridad", "detectadoEn",
                                               "resueltoEn", "origen", "resumenIA")}
            colectivo["afectados"] = len(c.get("usuariosAfectados", []))
            colectivo["antenasEnFalla"] = len(c.get("antenasEnFalla", []))
    return http.ok({
        "colectivo": colectivo,
        "incidencia": _vista(item, operador, completa=True),
        "historial": _historial(incidencia_id, operador),
        "zona": {
            "zonaId": item["zonaId"], "nombre": zona.get("nombre"), "tipo": zona.get("tipo"),
            "estadoRed": reglas.peor_estado(estados_antenas),
            "antenasConFalla": sum(1 for e in estados_antenas if e in ("CAIDA", "INHABILITADA")),
            "reportesActivos24h": len(activas),
            "usuariosAfectados24h": len({i["usuarioId"] for i in activas}),
        },
    })


@acceso.solo_operadores
def cambiar_estado(event, context):
    """PATCH /api/incidencias/{id}/estado (JWT + grupo `operadores`). El historial registra quién lo hizo."""
    incidencia_id = event["pathParameters"]["incidenciaId"]
    try:
        cuerpo = http.cuerpo_json(event)
    except ValueError as e:
        return http.error(400, str(e))
    nuevo = cuerpo.get("estado")
    comentario = str(cuerpo.get("comentario") or "")[:500]

    t = db.tabla("incidencias")
    item = t.get_item(Key={"incidenciaId": incidencia_id}).get("Item")
    if not item:
        return http.error(404, "Incidencia no encontrada")
    actual = item["estado"]
    if not reglas.transicion_valida(actual, nuevo):
        return http.error(409, f"No se puede pasar de {actual} a {nuevo}",
                          transicionesPermitidas=reglas.transiciones_permitidas(actual))

    ahora = util.ahora_iso()
    evento = historial.evento(incidencia_id, "INCIDENCIA", "CAMBIO_ESTADO", f"operador:{acceso.identidad(event)}",
                              detalle=comentario, estado_anterior=actual, estado_nuevo=nuevo, ocurrido_en=ahora)
    # H17: el cambio de estado y su historial van en UNA transacción (todo o nada): nunca hay estado sin rastro.
    try:
        db.transaccion([
            ("Update", "incidencias", {
                "Key": {"incidenciaId": incidencia_id},
                "UpdateExpression": "SET estado = :n, actualizadaEn = :t",
                "ConditionExpression": "estado = :a",  # evita pisar un cambio concurrente
                "ExpressionAttributeValues": {":n": nuevo, ":t": ahora, ":a": actual},
            }),
            ("Put", "historial", {"Item": evento, "ConditionExpression": "attribute_not_exists(sk)"}),
        ])
    except ClientError as e:
        if db.es_transaccion_cancelada(e) and db.motivos_cancelacion(e)[:1] == ["ConditionalCheckFailed"]:
            return http.error(409, "La incidencia cambió mientras tanto; recarga e inténtalo de nuevo")
        raise
    nuevo_item = {**item, "estado": nuevo, "actualizadaEn": ahora}
    if nuevo not in reglas.ESTADOS_INCIDENCIA_ACTIVOS:
        _liberar_dedup(item)  # resuelta: el usuario ya puede volver a reportar en esa zona
    return http.ok({"incidencia": _vista_operador(nuevo_item, completa=True)})
