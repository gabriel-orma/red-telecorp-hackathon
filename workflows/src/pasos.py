"""Pasos (Lambdas) de la Step Function `incidente-colectivo`.

Cada paso actualiza `pasoActual` del colectivo, para que el panel dibuje el flujo con el paso resaltado.
Entrada común: {"colectivoId": "COL-..."}.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos

from botocore.exceptions import ClientError

from telecorp import config, db, historial, notificador, reglas, util, zonas
import comun_colectivos as cc  # noqa: E402


def preparar_notificacion(event, context):
    """{colectivoId, estado, paso} → {destinatarios: [...]} para el Map de notificaciones."""
    cid, estado = event["colectivoId"], event["estado"]
    cc.marcar_paso(cid, event["paso"])
    col = cc.obtener(cid)
    return {"destinatarios": [{"colectivoId": cid, "incidenciaId": i, "estado": estado} for i in col.get("incidencias", [])]}


def notificar_uno(event, context):
    """Una iteración del Map: avisa a un usuario por los canales disponibles."""
    inc = db.tabla("incidencias").get_item(Key={"incidenciaId": event["incidenciaId"]}).get("Item")
    if not inc:
        return {"omitida": "incidencia inexistente"}
    canales = notificador.notificar(inc, event["estado"], event["colectivoId"])
    db.tabla("colectivos").update_item(Key={"incidenteColectivoId": event["colectivoId"]},
                                       UpdateExpression="ADD notificacionesEnviadas :uno",
                                       ExpressionAttributeValues={":uno": 1})
    return canales


def verificar_infraestructura(event, context):
    """Correlaciona con la red: antenas de la zona en falla en este momento."""
    cid = event["colectivoId"]
    cc.marcar_paso(cid, "VERIFICAR_INFRAESTRUCTURA")
    col = cc.obtener(cid)
    estados = cc.estados_antenas_zona(col["zonaId"])
    en_falla = [{"antenaId": a, "estado": e, "desde": util.ahora_iso()} for a, e in estados.items()
                if e in reglas.ESTADOS_ANTENA_FALLA]
    cc.agregar_antenas(col, en_falla)
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "COMENTARIO", "STEP_FUNCTION",
                        detalle=f"Verificación de infraestructura: {len(en_falla)} de {len(estados)} antenas en falla")
    return {"antenasEnFalla": len(col.get("antenasEnFalla", [])), "hayFalla": bool(col.get("antenasEnFalla")),
            "zona": (zonas.zona(col["zonaId"]) or {}).get("nombre", col["zonaId"])}


def priorizar(event, context):
    cid = event["colectivoId"]
    cc.marcar_paso(cid, "PRIORIZAR")
    col = cc.obtener(cid)
    puntaje, prioridad = _calcular(col)
    cc.actualizar(cid, prioridad=prioridad, puntajePrioridad=puntaje)
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "PRIORIDAD_ASIGNADA", "STEP_FUNCTION",
                        detalle=f"{prioridad} (puntaje {puntaje})")
    return {"prioridad": prioridad, "puntaje": puntaje, "critico": prioridad == "CRITICA",
            "afectados": len(col.get("usuariosAfectados", []))}


def resumir(event, context):
    """Resumen para el operador. TODO(D2): reemplazar la plantilla por la IA de la segunda nube."""
    cid = event["colectivoId"]
    cc.marcar_paso(cid, "RESUMIR")
    resumen = _texto_resumen(cc.obtener(cid))
    cc.actualizar(cid, resumenIA=resumen)
    return {"resumen": resumen, "fuente": "plantilla"}


def _texto_resumen(col: dict) -> str:
    zona = zonas.zona(col["zonaId"]) or {}
    antenas = ", ".join(f"{a['antenaId']} ({a['estado'].lower()})" for a in col.get("antenasEnFalla", [])) or "ninguna"
    clientes = f"{int(zona.get('clientesEstimados', 0)):,}".replace(",", ".")
    resumen = (f"{len(col.get('usuariosAfectados', []))} usuarios afectados en {zona.get('nombre', col['zonaId'])} "
               f"(zona {zona.get('tipo', '').lower()}, ~{clientes} clientes). "
               f"Antenas en falla: {antenas}. Prioridad {col.get('prioridad', '—')}.")
    return resumen


def confirmar(event, context):
    """El colectivo pasa a INCIDENCIA_CONFIRMADA y sus incidencias a EN_ATENCION (un equipo la atiende)."""
    cid = event["colectivoId"]
    col = cc.obtener(cid)
    cc.actualizar(cid, estado="INCIDENCIA_CONFIRMADA", pasoActual="CONFIRMAR", actualizadoEn=util.ahora_iso())
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "CAMBIO_ESTADO", "STEP_FUNCTION",
                        estado_anterior=col["estado"], estado_nuevo="INCIDENCIA_CONFIRMADA")
    _mover_incidencias(col, {"REGISTRADA", "EN_REVISION"}, "EN_ATENCION", "Asignada al equipo técnico del incidente colectivo")
    return {"estado": "INCIDENCIA_CONFIRMADA"}


def reverificar(event, context):
    """Bucle de monitoreo: ¿se restableció? (antenas normales o el operador lo marcó)."""
    cid = event["colectivoId"]
    iteracion = int(event.get("iteracion", 0)) + 1
    cc.marcar_paso(cid, "MONITOREAR")
    col = cc.obtener(cid)
    maximo = int(config.leer("reglas").get("colectivo", {}).get("maxIteraciones", 5760))

    if col.get("restablecimientoSolicitado"):
        return {"restablecido": True, "via": "OPERADOR", "iteracion": iteracion, "agotado": False}

    estados = cc.estados_antenas_zona(col["zonaId"])
    nuevas = [{"antenaId": a, "estado": e, "desde": util.ahora_iso()} for a, e in estados.items()
              if e in reglas.ESTADOS_ANTENA_FALLA]
    antes = len(col.get("antenasEnFalla", []))
    cc.agregar_antenas(col, nuevas)  # fallas que aparecieron durante el monitoreo
    _repriorizar(col)  # el tiempo activo sube el puntaje en cada vuelta del monitoreo
    afectadas = [a["antenaId"] for a in col.get("antenasEnFalla", [])]
    if afectadas and all(estados.get(a) not in reglas.ESTADOS_ANTENA_FALLA for a in afectadas):
        return {"restablecido": True, "via": "AUTOMATICO", "iteracion": iteracion, "agotado": False}
    return {"restablecido": False, "iteracion": iteracion, "agotado": iteracion >= maximo,
            "afectados": len(col.get("usuariosAfectados", []))}


def _calcular(col: dict) -> tuple:
    """Puntaje con afectados, criticidad de la zona, antenas en falla y horas activo (TODO D7: pesos en SSM)."""
    cfg = config.leer("reglas").get("prioridad", {})
    horas = (util.ahora() - util.parse_iso(col["detectadoEn"])).total_seconds() / 3600 * float(col.get("factorTiempo", 1))
    return reglas.calcular_prioridad(len(col.get("usuariosAfectados", [])), zonas.criticidad(col["zonaId"]),
                                     len(col.get("antenasEnFalla", [])), cfg, horas_activo=horas)


def _repriorizar(col: dict) -> None:
    """Recalcula el puntaje (sube con el tiempo). Solo deja historial si cambia el NIVEL; si escala a CRÍTICA, alerta al NOC."""
    import os
    import boto3
    puntaje, prioridad = _calcular(col)
    previa = col.get("prioridad")
    if puntaje == float(col.get("puntajePrioridad", 0)):
        return
    col.update(prioridad=prioridad, puntajePrioridad=puntaje)
    cc.actualizar(col["incidenteColectivoId"], prioridad=prioridad, puntajePrioridad=puntaje,
                  **({"resumenIA": _texto_resumen(col)} if prioridad != previa else {}))
    if prioridad == previa:
        return
    historial.registrar(col["incidenteColectivoId"], "INCIDENTE_COLECTIVO", "PRIORIDAD_ASIGNADA", "STEP_FUNCTION",
                        detalle=f"Re-priorizado: {previa} → {prioridad} (puntaje {puntaje})")
    if prioridad == "CRITICA" and previa != "CRITICA" and os.environ.get("TOPICO_ALERTAS"):
        boto3.client("sns").publish(
            TopicArn=os.environ["TOPICO_ALERTAS"], Subject="Red TeleCorp - Incidente escalado a CRITICO",
            Message=f"{col['incidenteColectivoId']} en {(zonas.zona(col['zonaId']) or {}).get('nombre')}: "
                    f"{len(col.get('usuariosAfectados', []))} afectados, {len(col.get('antenasEnFalla', []))} antenas en falla.")


def restablecer(event, context):
    cid = event["colectivoId"]
    col = cc.obtener(cid)
    via = event.get("via", "AUTOMATICO")
    cc.actualizar(cid, estado="SERVICIO_RESTABLECIDO", pasoActual="RESTABLECER", actualizadoEn=util.ahora_iso())
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "CAMBIO_ESTADO", "STEP_FUNCTION",
                        detalle="Restablecido por el operador" if via == "OPERADOR" else "Antenas de la zona normalizadas",
                        estado_anterior=col["estado"], estado_nuevo="SERVICIO_RESTABLECIDO")
    return {"via": via}


def cerrar(event, context):
    cid = event["colectivoId"]
    col = cc.obtener(cid)
    ahora = util.ahora_iso()
    _mover_incidencias(col, reglas.ESTADOS_INCIDENCIA_ACTIVOS, "SOLUCIONADA", "Servicio restablecido en la zona",
                       liberar=True)
    minutos = round((util.ahora() - util.parse_iso(col["detectadoEn"])).total_seconds() / 60, 1)
    cc.actualizar(cid, estado="CERRADO", pasoActual="CERRADO", resueltoEn=ahora, actualizadoEn=ahora,
                  duracionMinutos=minutos)
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "CAMBIO_ESTADO", "STEP_FUNCTION", detalle=f"Duración: {minutos} min",
                        estado_anterior=col["estado"], estado_nuevo="CERRADO")
    cc.liberar_lock(col["zonaId"], cid)
    return {"duracionMinutos": minutos}


def sin_resolver(event, context):
    cid = event["colectivoId"]
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "COMENTARIO", "STEP_FUNCTION",
                        detalle="Tiempo máximo de monitoreo agotado: requiere atención manual")
    cc.marcar_paso(cid, "MONITOREAR")
    return {}


def _mover_incidencias(col: dict, desde: set, hacia: str, detalle: str, liberar: bool = False) -> None:
    t = db.tabla("incidencias")
    for iid in col.get("incidencias", []):
        inc = t.get_item(Key={"incidenciaId": iid}).get("Item")
        if not inc or inc["estado"] not in desde:
            continue
        ahora = util.ahora_iso()
        try:
            t.update_item(Key={"incidenciaId": iid}, UpdateExpression="SET estado = :n, actualizadaEn = :t",
                          ConditionExpression="estado = :a",
                          ExpressionAttributeValues={":n": hacia, ":t": ahora, ":a": inc["estado"]})
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                continue  # un operador la cambió a la vez
            raise
        historial.registrar(iid, "INCIDENCIA", "CAMBIO_ESTADO", "STEP_FUNCTION", detalle=detalle,
                            estado_anterior=inc["estado"], estado_nuevo=hacia, ocurrido_en=ahora)
        if liberar:
            cc.liberar_dedup_usuario(inc)
