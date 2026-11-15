"""Pasos (Lambdas) de la Step Function `incidente-colectivo`.

Cada paso actualiza `pasoActual` del colectivo, para que el panel dibuje el flujo con el paso resaltado.
Entrada común: {"colectivoId": "COL-..."}.

Diseño (ver workflows/README.md):
- Avisos por LOTES: `preparar_notificacion` solo devuelve la lista de lotes (unos pocos bytes por lote) y el Map procesa
  un lote por iteración con `notificar_lote`. Así la ejecución no depende del número de afectados (límites de 256 KiB por
  estado y 25.000 eventos de historial).
- Idempotencia: `telecorp.notificador.notificar` marca (incidencia, estado) en `dedup` antes de enviar.
- El monitoreo está acotado (iteraciones y tiempo) y decide con `monitoreo.decidir` (reglas puras).
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(__file__))  # el handler se carga como src/<modulo>: permitir imports hermanos

import os
from datetime import timedelta

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from telecorp import config, db, historial, notificador, reglas, util, zonas
from telecorp.nube2 import azure_maps, ia
import comun_colectivos as cc  # noqa: E402
import monitoreo  # noqa: E402

LOTE_AVISOS = 50              # destinatarios por iteración del Map (una Lambda por lote)
SILENCIO_MIN = 60             # minutos sin reportes nuevos para cerrar un colectivo sin antenas en falla
MAX_MONITOREO_MIN = 2880      # 48 h de monitoreo como máximo, luego atención manual
MAX_ITERACIONES = 2000        # 2000 × 9 eventos = 18.000 < 25.000 (límite de historial de Step Functions)


class AvisosIncompletos(Exception):
    """Un lote no pudo avisar a todos: Step Functions reintenta (los ya avisados se omiten) y, si persiste, sigue sin abortar."""


def _cfg() -> dict:
    return config.leer("reglas").get("colectivo", {})


# ---------------------------------------------------------------- Avisos (por lotes e idempotentes)
def preparar_notificacion(event, context):
    """{colectivoId, estado, paso} → lotes para el Map. Devuelve solo [{colectivoId, estado, lote, loteTam}], no usuarios."""
    cid, estado = event["colectivoId"], event["estado"]
    cc.marcar_paso(cid, event["paso"])
    col = cc.obtener(cid)
    tam = max(1, int(_cfg().get("loteAvisos", LOTE_AVISOS)))
    total = len(col.get("incidencias", []))
    return {"total": total, "loteTam": tam,
            "lotes": [{"colectivoId": cid, "estado": estado, "lote": i, "loteTam": tam}
                      for i in range(monitoreo.cantidad_lotes(total, tam))]}


def notificar_uno(event, context):
    """Avisa a un usuario por los canales disponibles, una sola vez por (incidencia, estado)."""
    inc = db.tabla("incidencias").get_item(Key={"incidenciaId": event["incidenciaId"]}).get("Item")
    if not inc:
        return {"omitida": "incidencia inexistente"}
    return notificador.notificar(inc, event["estado"], event["colectivoId"])


def notificar_lote(event, context):
    """Una iteración del Map: avisa a los usuarios del lote. Un fallo individual NO aborta al resto del lote."""
    cid, estado, lote, tam = event["colectivoId"], event["estado"], int(event["lote"]), int(event["loteTam"])
    ids = cc.obtener(cid).get("incidencias", [])[lote * tam:(lote + 1) * tam]  # la lista solo crece: los índices son estables
    enviados = omitidos = 0
    fallidos = []
    for iid in ids:
        try:
            r = notificar_uno({"colectivoId": cid, "incidenciaId": iid, "estado": estado}, None)
        except Exception:  # noqa: BLE001 - se reintenta el lote completo; los ya avisados se omiten
            fallidos.append(iid)
            continue
        if "omitido" in r or "omitida" in r:
            omitidos += 1
        else:
            enviados += 1
    if enviados:
        db.tabla("colectivos").update_item(Key={"incidenteColectivoId": cid}, UpdateExpression="ADD notificacionesEnviadas :n",
                                           ExpressionAttributeValues={":n": enviados})
    if fallidos:
        historial.registrar(cid, "INCIDENTE_COLECTIVO", "COMENTARIO", "STEP_FUNCTION",
                            detalle=f"Lote {lote}: {len(fallidos)} de {len(ids)} avisos '{estado}' fallaron")
        raise AvisosIncompletos(f"lote {lote}: {len(fallidos)} de {len(ids)} sin avisar")
    return {"lote": lote, "enviados": enviados, "omitidos": omitidos}


# ---------------------------------------------------------------- Verificación, prioridad y resumen
def verificar_infraestructura(event, context):
    """Correlaciona con la red: antenas de la zona en falla o saturadas en este momento (H24). El flujo decide con esto."""
    cid = event["colectivoId"]
    cc.marcar_paso(cid, "VERIFICAR_INFRAESTRUCTURA")
    col = cc.obtener(cid)
    estados, desde = cc.antenas_zona(col["zonaId"])
    en_falla = [{"antenaId": a, "estado": e, "desde": desde.get(a) or util.ahora_iso()} for a, e in estados.items()
                if e in reglas.ESTADOS_ANTENA_VERIFICACION]
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
    """Análisis del incidente para el operador: IA (Gemini) sobre DATOS AGREGADOS + clima de Azure Maps.

    Si la IA, Azure Maps o sus secretos no están disponibles el flujo NO se bloquea: `ia.analizar_colectivo` devuelve el
    análisis determinista (`fuente: "REGLAS"`), y sin clima el análisis sigue. `resumenIA` se conserva (texto corto)."""
    cid = event["colectivoId"]
    cc.marcar_paso(cid, "RESUMIR")
    analisis = _generar_analisis(cc.obtener(cid))
    return {"resumen": analisis["resumen"], "fuente": analisis.get("fuente")}


def _generar_analisis(col: dict) -> dict:
    """Genera y guarda `analisisIA` (+ `resumenIA`) del colectivo. Anota sobre qué datos se hizo (`basadoEn`) para saber
    cuándo queda desactualizado. Nunca lanza: ante cualquier fallo de la IA o de Azure Maps usa la plantilla determinista."""
    cid = col["incidenteColectivoId"]
    try:
        analisis = ia.analizar_colectivo(_contexto_analisis(col))
    except Exception as e:  # noqa: BLE001 - nunca debe romper el flujo
        print(f"resumir: análisis no disponible ({type(e).__name__})")
        analisis = ia.analisis_reglas(_contexto_analisis(col, con_clima=False))
    previo = col.get("analisisIA") or {}
    if analisis.get("fuente") != "IA" and previo.get("fuente") == "IA":
        # Una regeneración que cae a reglas (cupo agotado, modelo caído) NO pisa un análisis de IA válido: se conserva y se
        # reintentará en la próxima vuelta (no se actualiza `basadoEn`).
        return {**previo, "resumen": (previo.get("resumen") or "")[:400]}
    analisis["basadoEn"] = {"afectados": len(col.get("usuariosAfectados", [])), "antenasEnFalla": len(col.get("antenasEnFalla", []))}
    resumen = (analisis.get("resumen") or _texto_resumen(col))[:400]
    cc.actualizar(cid, resumenIA=resumen, analisisIA=analisis)
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "COMENTARIO", "IA" if analisis.get("fuente") == "IA" else "STEP_FUNCTION",
                        detalle=f"Análisis {analisis.get('fuente')}: {len(analisis.get('hipotesisCausa', []))} hipótesis, "
                                f"confianza {analisis.get('confianza')}")
    return {**analisis, "resumen": resumen}


def _refrescar_analisis(col: dict) -> bool:
    """Si desde el último análisis cambiaron los afectados o las antenas en falla (p. ej. las antenas cayeron ANTES de los
    reportes y el colectivo se abrió con 0 usuarios), lo vuelve a generar. Devuelve True si lo regeneró. Nunca lanza."""
    try:
        previo = (col.get("analisisIA") or {}).get("basadoEn") or {}
        ahora = {"afectados": len(col.get("usuariosAfectados", [])), "antenasEnFalla": len(col.get("antenasEnFalla", []))}
        if col.get("analisisIA") and all(int(previo.get(k, -1)) == v for k, v in ahora.items()):
            return False
        _generar_analisis(col)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"reverificar: no se pudo refrescar el análisis ({type(e).__name__})")
        return False


def _simulacion_activa() -> bool:
    """¿Hay un escenario de demo en curso o fallas forzadas en el simulador? Entonces los datos son simulados."""
    for parametro, campo in (("escenario", "activo"), ("simulador", "fallas")):
        try:                                   # cada parámetro por separado: que falte uno no debe ocultar el otro
            if config.leer(parametro, usar_cache=False).get(campo):
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _contexto_analisis(col: dict, con_clima: bool = True) -> dict:
    """Solo agregados (R3): conteos, estados de antenas, zona, clima. Sin ids de usuarios, correos ni descripciones."""
    zona = zonas.zona(col["zonaId"]) or {}
    centro = zona.get("centro") or {}
    tipos: dict = {}
    simulados = total = 0
    for inc in db.obtener_varios("incidencias", "incidenciaId", col.get("incidencias", [])[:300]):
        tipos[inc.get("tipo", "OTRO")] = tipos.get(inc.get("tipo", "OTRO"), 0) + 1
        total += 1
        simulados += bool((inc.get("reporte") or {}).get("simulado"))
    clima = None
    if con_clima and centro.get("lat") is not None:
        try:
            clima = azure_maps.clima_actual(float(centro["lat"]), float(centro["lng"]))
        except Exception:  # noqa: BLE001
            clima = None
    ahora = util.ahora()
    return {
        "zonaId": col["zonaId"],
        "zona": {"nombre": zona.get("nombre"), "tipo": zona.get("tipo"), "criticidad": zonas.criticidad(col["zonaId"]),
                 "clientesEstimados": zona.get("clientesEstimados")},
        "afectados": len(col.get("usuariosAfectados", [])), "tiposReporte": tipos,
        "antenasEnFalla": [{"antenaId": a.get("antenaId"), "estado": a.get("estado")} for a in col.get("antenasEnFalla", [])],
        "antenasZona": len(zona.get("antenas", [])), "prioridad": col.get("prioridad"), "origen": col.get("origen"),
        "duracionMin": round((ahora - util.parse_iso(col["detectadoEn"])).total_seconds() / 60, 1),
        "deteccionAnticipadaMin": reglas.deteccion_anticipada_min(col.get("primeraFallaEn"), col.get("primerReporteEn")),
        "clima": clima, "horaLocal": (ahora + timedelta(hours=-5)).strftime("%H:%M"),   # Lima (UTC-5)
        # No se envía al modelo (`_contexto_para_prompt` elige sus campos): solo decide si se gasta cuota de la IA.
        "simulacion": bool(total and simulados * 2 >= total) or _simulacion_activa(),
    }


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


# ---------------------------------------------------------------- Monitoreo
def reverificar(event, context):
    """Una vuelta del monitoreo: ¿se restableció?, ¿hay que escalar?, ¿se agotó el tiempo? (decide `monitoreo.decidir`)."""
    cid = event["colectivoId"]
    iteracion = int(event.get("iteracion", 0)) + 1
    cc.marcar_paso(cid, "MONITOREAR")
    col = cc.obtener(cid)
    cfg = _cfg()

    if col.get("restablecimientoSolicitado"):  # el operador manda: no depende de leer antenas
        return {"restablecido": True, "via": "OPERADOR", "iteracion": iteracion, "agotado": False, "escalar": False}

    estados, desde = cc.antenas_zona(col["zonaId"])
    nuevas = [{"antenaId": a, "estado": e, "desde": desde.get(a) or util.ahora_iso()} for a, e in estados.items()
              if e in reglas.ESTADOS_ANTENA_VERIFICACION]
    antes = len(col.get("antenasEnFalla", []))
    cc.agregar_antenas(col, nuevas)  # fallas que aparecieron durante el monitoreo
    col = cc.obtener(cid)             # afectados y antenas al día (los reportes siguen llegando mientras se monitorea)
    _refrescar_analisis(col)
    _repriorizar(col)  # el tiempo activo sube el puntaje en cada vuelta del monitoreo
    afectadas = [a["antenaId"] for a in col.get("antenasEnFalla", [])]
    silencio = int(cfg.get("cierreSinReportesMinutos", SILENCIO_MIN))
    decision = monitoreo.decidir(
        solicitado=False, afectadas=afectadas, estados=estados,
        confirmada=col.get("estado") == "INCIDENCIA_CONFIRMADA",
        sin_reportes_recientes=(not afectadas) and not _hay_reportes_recientes(col["zonaId"], silencio),
        iteracion=iteracion, max_iteraciones=int(cfg.get("maxIteraciones", MAX_ITERACIONES)),
        minutos_transcurridos=(util.ahora() - util.parse_iso(col["detectadoEn"])).total_seconds() / 60,
        max_minutos=float(cfg.get("maxMonitoreoMinutos", MAX_MONITOREO_MIN)))
    return {**decision, "iteracion": iteracion, "afectados": len(col.get("usuariosAfectados", []))}


def _hay_reportes_recientes(zona_id: str, minutos: int) -> bool:
    """¿Entró algún reporte en la zona en los últimos `minutos`? (GSI zona-fecha por tiempo de ingesta; 1 consulta)."""
    r = db.tabla("incidencias").query(
        IndexName="zona-fecha", Limit=1, Select="COUNT",
        KeyConditionExpression=Key("zonaId").eq(zona_id) & Key("creadaEn").gte(util.hace_iso(minutes=minutos)))
    return r["Count"] > 0 or "LastEvaluatedKey" in r


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
                  **({"resumenIA": _texto_resumen(col)} if prioridad != previa and not col.get("analisisIA") else {}))
    if prioridad == previa:
        return
    historial.registrar(col["incidenteColectivoId"], "INCIDENTE_COLECTIVO", "PRIORIDAD_ASIGNADA", "STEP_FUNCTION",
                        detalle=f"Re-priorizado: {previa} → {prioridad} (puntaje {puntaje})")
    if prioridad == "CRITICA" and previa != "CRITICA" and os.environ.get("TOPICO_ALERTAS"):
        boto3.client("sns").publish(
            TopicArn=os.environ["TOPICO_ALERTAS"], Subject="Red TeleCorp - Incidente escalado a CRITICO",
            Message=f"{col['incidenteColectivoId']} en {(zonas.zona(col['zonaId']) or {}).get('nombre')}: "
                    f"{len(col.get('usuariosAfectados', []))} afectados, {len(col.get('antenasEnFalla', []))} antenas en falla.")


# ---------------------------------------------------------------- Cierre y errores
_DETALLE_RESTABLECIDO = {
    "OPERADOR": "Restablecido por el operador",
    "AUTOMATICO": "Antenas de la zona normalizadas",
    "SIN_REPORTES": "Sin falla de red y sin reportes nuevos en la zona: se da por resuelto",
}


def restablecer(event, context):
    cid = event["colectivoId"]
    col = cc.obtener(cid)
    via = event.get("via", "AUTOMATICO")
    cc.actualizar(cid, estado="SERVICIO_RESTABLECIDO", pasoActual="RESTABLECER", actualizadoEn=util.ahora_iso())
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "CAMBIO_ESTADO", "STEP_FUNCTION",
                        detalle=_DETALLE_RESTABLECIDO.get(via, via), estado_anterior=col["estado"],
                        estado_nuevo="SERVICIO_RESTABLECIDO")
    return {"via": via}


def cerrar(event, context):
    """Cierra el colectivo. Quien se sumó después del snapshot de avisos recibe aquí su aviso de 'restablecido' (idempotente)."""
    cid = event["colectivoId"]
    col = cc.obtener(cid)
    ahora = util.ahora_iso()
    def avisar_rezagado(inc):
        try:
            notificador.notificar(inc, "SERVICIO_RESTABLECIDO", cid)  # no-op si ya recibió el aviso (idempotente)
        except Exception:  # noqa: BLE001 - un aviso de cortesía no debe impedir cerrar el incidente
            pass

    _mover_incidencias(col, reglas.ESTADOS_INCIDENCIA_ACTIVOS, "SOLUCIONADA", "Servicio restablecido en la zona",
                       liberar=True, antes=avisar_rezagado)
    minutos = round((util.ahora() - util.parse_iso(col["detectadoEn"])).total_seconds() / 60, 1)
    cc.actualizar(cid, estado="CERRADO", pasoActual="CERRADO", resueltoEn=ahora, actualizadoEn=ahora,
                  duracionMinutos=minutos)
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "CAMBIO_ESTADO", "STEP_FUNCTION", detalle=f"Duración: {minutos} min",
                        estado_anterior=col["estado"], estado_nuevo="CERRADO")
    cc.liberar_lock(col["zonaId"], cid)
    return {"duracionMinutos": minutos}


def sin_resolver(event, context):
    """El monitoreo se agotó sin restablecerse: el colectivo pasa a atención manual y la zona deja de estar bloqueada."""
    _atencion_manual(event["colectivoId"], "Tiempo máximo de monitoreo agotado: requiere atención manual")
    return {}


def manejar_fallo(event, context):
    """Catch global: ante un error irrecuperable del flujo, el colectivo queda consistente (atención manual) y sin candado."""
    err = event.get("error") or {}
    _atencion_manual(event["colectivoId"], f"El flujo automático falló ({err.get('Error', 'error')}); requiere atención manual",
                     causa=str(err.get("Cause", ""))[:300])
    return {}


def _atencion_manual(cid: str, detalle: str, causa: str = "") -> None:
    try:
        col = cc.obtener(cid)
    except ValueError:
        return
    if col.get("estado") in ("CERRADO", "REQUIERE_ATENCION"):
        return  # idempotente (reintentos del propio manejador)
    ahora = util.ahora_iso()
    cc.actualizar(cid, estado="REQUIERE_ATENCION", pasoActual="ATENCION_MANUAL", actualizadoEn=ahora)
    historial.registrar(cid, "INCIDENTE_COLECTIVO", "CAMBIO_ESTADO", "STEP_FUNCTION",
                        detalle=detalle + (f" · {causa}" if causa else ""),
                        estado_anterior=col["estado"], estado_nuevo="REQUIERE_ATENCION")
    cc.liberar_lock(col["zonaId"], cid)


def _mover_incidencias(col: dict, desde: set, hacia: str, detalle: str, liberar: bool = False, antes=None) -> None:
    t = db.tabla("incidencias")
    for iid in col.get("incidencias", []):
        inc = t.get_item(Key={"incidenciaId": iid}).get("Item")
        if not inc or inc["estado"] not in desde:
            continue
        if antes:
            antes(inc)
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
