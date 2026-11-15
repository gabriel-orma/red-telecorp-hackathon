"""Operaciones sobre incidentes colectivos compartidas por el detector y los pasos de la Step Function.

Garantías (cada una tiene su prueba en workflows/tests/test_deteccion.py):
- Un solo colectivo abierto por zona: el candado `LOCK#COLECTIVO#<zona>`, el colectivo, su historial `CREADO` y la
  etiqueta de cada incidencia se escriben en UNA transacción de DynamoDB (todo o nada). No hay candado huérfano
  ni colectivo a medias.
- La Step Function se arranca con `name=<colectivoId>`: es idempotente y se puede reintentar (cura al "colectivo zombi").
- Agrupar incidencias es un `list_append` condicional y atómico por incidencia (sin leer antes): dos detectores en
  paralelo no se pisan ni entran en conflicto, y reintentar no duplica. Las antenas (pocas por colectivo) usan control
  de versión: escritura condicional + relectura.
- Datos operativos y simulados NUNCA se mezclan (`reglas.es_simulado`): cada modo tiene su propia ventana y su propio candado
  (`...~SIM`). Nueve vecinos reales + uno simulado no forman un colectivo, y una Tormenta no consume ni bloquea la zona
  de los reportes reales. El colectivo queda marcado `simulado: true` y todo lo que lo lee (analítica, recurrencia, estado
  público) lo separa. Sin indicar `sim`, todo funciona como antes (modo operativo).
- Conteo exacto de usuarios sin depender del GSI (eventualmente consistente): la "ventana" de la zona
  (`VENTANA#<zona>` en la tabla `dedup`) es un mapa usuario → {ts, inc} que se actualiza de forma atómica y se lee con
  consistencia fuerte; el detector la une con lo que ve el GSI.
"""
import json
import os
import random
import time

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from telecorp import db, escenarios, historial, notificador, reglas, util, zonas

_sfn = boto3.client("stepfunctions")
LOCK_DIAS = 7
INTENTOS_VERSION = 25
MAX_INCIDENCIAS_EN_TRANSACCION = 40  # 2 ítems por incidencia (etiqueta + historial) + 2 fijos ≤ 100 (límite de DynamoDB)

# H11. El enunciado pide reportes "relacionados con el servicio". Los seis tipos del catálogo lo son por construcción;
# `OTRO` es texto libre sin clasificar y no cuenta para disparar un colectivo (sí se suma a uno ya abierto).
# La IA puede REINCORPORARLO si clasificó el texto como problema del servicio con confianza ≥ 0,8 (`iaTriage`, guardado por el
# worker de ingesta): ver `reglas.triage_ia_confirma_servicio`. Solo suma; si la IA falla, OTRO sigue sin contar.
TIPOS_SIN_RELACION_DEMOSTRADA = {"OTRO"}


def relacionada_con_servicio(incidencia: dict) -> bool:
    if incidencia.get("tipo") not in TIPOS_SIN_RELACION_DEMOSTRADA:
        return True
    return reglas.triage_ia_confirma_servicio(incidencia.get("iaTriage"))


# ---------------- Lectura ----------------
def obtener(colectivo_id: str) -> dict:
    item = db.tabla("colectivos").get_item(Key={"incidenteColectivoId": colectivo_id}, ConsistentRead=True).get("Item")
    if not item:
        raise ValueError(f"Colectivo no encontrado: {colectivo_id}")
    return item


def incidencias_ventana_zona(zona_id: str, horas: int, sim: bool = False) -> list:
    """Incidencias de la zona dentro de la ventana (creadaEn ESTRICTAMENTE posterior a ahora-horas), de CUALQUIER
    estado (H10: un reporte que el operador ya cerró sigue siendo un usuario que reportó en <24 h) y que todavía
    no pertenecen a un colectivo. Solo las del modo pedido (operativas o simuladas). Lee el GSI (eventualmente consistente)."""
    corte = util.hace_iso(hours=horas)
    t, items, kwargs = db.tabla("incidencias"), [], {}
    while True:
        r = t.query(IndexName="zona-fecha",
                    KeyConditionExpression=Key("zonaId").eq(zona_id) & Key("creadaEn").gt(corte), **kwargs)
        items.extend(i for i in r["Items"] if i["creadaEn"] > corte and not i.get("incidenteColectivoId")
                     and reglas.es_simulado(i) == sim)
        if "LastEvaluatedKey" not in r:
            return items
        kwargs["ExclusiveStartKey"] = r["LastEvaluatedKey"]


def incidencias_activas_zona(zona_id: str, horas: int, sim: bool = False) -> list:
    """Solo las que siguen abiertas (para sumarlas a un colectivo creado por métricas de antena)."""
    return [i for i in incidencias_ventana_zona(zona_id, horas, sim) if i.get("estado") in reglas.ESTADOS_INCIDENCIA_ACTIVOS]


def cargar_incidencias(ids: list, horas: int) -> list:
    """Lee (consistente) incidencias por id; descarta las que no existen, ya están en un colectivo o salieron de la ventana."""
    corte = util.hace_iso(hours=horas)
    return [i for i in db.obtener_varios("incidencias", "incidenciaId", ids)
            if not i.get("incidenteColectivoId") and i["creadaEn"] > corte]


def antenas_zona(zona_id: str) -> tuple:
    """({antenaId: estado}, {antenaId: estadoDesde}). `estadoDesde` es cuándo entró la antena en su estado actual (lo escribe el
    clasificador): la «detección anticipada» se mide con ese instante, no con el momento en que la verificación la vio."""
    t = db.tabla("antenas")
    estados, desde = {}, {}
    for a in (zonas.zona(zona_id) or {}).get("antenas", []):
        item = t.get_item(Key={"antenaId": a["antenaId"]}).get("Item", {})
        estados[a["antenaId"]] = item.get("estado", "SIN_DATOS")
        if item.get("estadoDesde"):
            desde[a["antenaId"]] = item["estadoDesde"]
    return estados, desde


def estados_antenas_zona(zona_id: str) -> dict:
    return antenas_zona(zona_id)[0]


# ---------------- Ventana por zona (conteo exacto sin GSI) ----------------
SUFIJO_SIMULACION = "~SIM"


def _clave_ventana(zona_id: str, sim: bool = False) -> str:
    return f"VENTANA#{zona_id}{SUFIJO_SIMULACION if sim else ''}"


def _vigentes(usuarios: dict, horas: int) -> dict:
    corte = util.hace_iso(hours=horas)
    return {u: e for u, e in (usuarios or {}).items() if str(e.get("ts", "")) > corte}


def leer_ventana(zona_id: str, horas: int, sim: bool = False) -> dict:
    """{usuarioId: {ts, inc}} de los usuarios con reporte vigente aún sin colectivo (lectura fuertemente consistente)."""
    item = db.tabla("dedup").get_item(Key={"clave": _clave_ventana(zona_id, sim)}, ConsistentRead=True).get("Item") or {}
    return _vigentes(item.get("usuarios"), horas)


def registrar_en_ventana(zona_id: str, incidencia: dict, horas: int, sim: bool = False) -> dict:
    """Anota al usuario en la ventana de la zona con UN update atómico y devuelve la ventana vigente resultante.

    El `ReturnValues=ALL_NEW` de DynamoDB refleja todas las escrituras confirmadas antes de ésta: de dos detectores
    que anotan al 9.º y al 10.º usuario a la vez, el que confirma último ve a los dos, sin importar el GSI.
    """
    t = db.tabla("dedup")
    entrada = {"ts": incidencia["creadaEn"], "inc": incidencia["incidenciaId"]}
    expira = int(time.time()) + (horas + 1) * 3600
    kw = dict(Key={"clave": _clave_ventana(zona_id, sim)}, UpdateExpression="SET usuarios.#u = :e, expiraEn = :x",
              ExpressionAttributeNames={"#u": incidencia["usuarioId"]},
              ExpressionAttributeValues={":e": entrada, ":x": expira}, ReturnValues="ALL_NEW")
    try:
        r = t.update_item(**kw)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ValidationException":
            raise
        # Primera escritura de la zona: el mapa aún no existe. Se crea (idempotente) y se repite.
        t.update_item(Key=kw["Key"], UpdateExpression="SET usuarios = if_not_exists(usuarios, :m), expiraEn = :x",
                      ExpressionAttributeValues={":m": {}, ":x": expira})
        r = t.update_item(**kw)
    todos = r["Attributes"].get("usuarios", {})
    vigentes = _vigentes(todos, horas)
    quitar_de_ventana(zona_id, {u: e for u, e in todos.items() if u not in vigentes}, sim)  # poda de caducados
    return vigentes


def quitar_de_ventana(zona_id: str, entradas: dict, sim: bool = False) -> None:
    """Quita usuarios de la ventana solo si siguen siendo la misma entrada (no pisa a un reporte nuevo). Mejor esfuerzo."""
    entradas = {u: e for u, e in (entradas or {}).items() if e.get("inc")}
    if not entradas:
        return

    def _quitar(par: list) -> None:
        nombres = {f"#k{n}": u for n, (u, _) in enumerate(par)}
        valores = {f":i{n}": e["inc"] for n, (_, e) in enumerate(par)}
        db.tabla("dedup").update_item(
            Key={"clave": _clave_ventana(zona_id, sim)},
            UpdateExpression="REMOVE " + ", ".join(f"usuarios.#k{n}" for n in range(len(par))),
            ConditionExpression=" AND ".join(f"usuarios.#k{n}.inc = :i{n}" for n in range(len(par))),
            ExpressionAttributeNames=nombres, ExpressionAttributeValues=valores)

    items = list(entradas.items())
    try:
        _quitar(items[:50])
    except ClientError:
        for par in items[:50]:  # alguna entrada cambió: una por una
            try:
                _quitar([par])
            except ClientError:
                pass


# ---------------- Candado: un solo colectivo abierto por zona ----------------
def _clave_lock(zona_id: str, sim: bool = False) -> str:
    return f"LOCK#COLECTIVO#{zona_id}{SUFIJO_SIMULACION if sim else ''}"


def colectivo_abierto(zona_id: str, sim: bool = False) -> str | None:
    """Id del colectivo abierto de la zona (en el modo operativo o en el simulado), o None. Un candado cuyo colectivo no existe (o ya cerró) se considera
    huérfano: se libera y la zona vuelve a poder detectar (H05)."""
    item = db.tabla("dedup").get_item(Key={"clave": _clave_lock(zona_id, sim)}, ConsistentRead=True).get("Item")
    if not item or int(item.get("expiraEn", 0)) <= time.time():
        return None
    colectivo_id = item["incidenciaId"]  # la tabla dedup guarda el id en el atributo incidenciaId
    col = db.tabla("colectivos").get_item(Key={"incidenteColectivoId": colectivo_id}, ConsistentRead=True).get("Item")
    if not col or col.get("estado") == "CERRADO":
        liberar_lock(zona_id, colectivo_id, sim)
        return None
    return colectivo_id


def tomar_lock(zona_id: str, colectivo_id: str, sim: bool = False) -> str | None:
    """Reserva la zona (sin transacción). La creación normal usa `crear`, que toma el candado junto con el colectivo."""
    ahora = int(time.time())
    try:
        db.tabla("dedup").put_item(
            Item={"clave": _clave_lock(zona_id, sim), "incidenciaId": colectivo_id, "expiraEn": ahora + LOCK_DIAS * 86400},
            ConditionExpression="attribute_not_exists(clave) OR expiraEn < :ahora",
            ExpressionAttributeValues={":ahora": ahora},
        )
        return None
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return colectivo_abierto(zona_id, sim)


def liberar_lock(zona_id: str, colectivo_id: str, sim: bool = False) -> None:
    try:
        db.tabla("dedup").delete_item(Key={"clave": _clave_lock(zona_id, sim)}, ConditionExpression="incidenciaId = :c",
                                      ExpressionAttributeValues={":c": colectivo_id})
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def liberar_dedup_usuario(incidencia: dict) -> None:
    try:
        db.tabla("dedup").delete_item(Key={"clave": db.clave_dedup_usuario(incidencia["usuarioId"], incidencia["zonaId"])},
                                      ConditionExpression="incidenciaId = :i",
                                      ExpressionAttributeValues={":i": incidencia["incidenciaId"]})
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


# ---------------- Escritura ----------------
def actualizar(colectivo_id: str, **campos) -> None:
    nombres = {f"#{k}": k for k in campos}
    valores = {f":{k}": v for k, v in campos.items()}
    db.tabla("colectivos").update_item(
        Key={"incidenteColectivoId": colectivo_id},
        UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in campos),
        ExpressionAttributeNames=nombres, ExpressionAttributeValues=util.a_dynamo(valores),
    )


def marcar_paso(colectivo_id: str, paso: str) -> None:
    actualizar(colectivo_id, pasoActual=paso, actualizadoEn=util.ahora_iso())


def _escribir_con_version(col: dict, cambios: dict) -> bool:
    """SET de `cambios` solo si nadie escribió las listas desde que `col` se leyó. Si falla, refresca `col` (en el sitio)
    con la versión vigente y devuelve False: el llamador recalcula y reintenta."""
    cid, v = col["incidenteColectivoId"], int(col.get("version", 0))
    campos = {**cambios, "version": v + 1}
    try:
        db.tabla("colectivos").update_item(
            Key={"incidenteColectivoId": cid},
            UpdateExpression="SET " + ", ".join(f"#{k} = :{k}" for k in campos),
            ConditionExpression="#version = :v0" if v else "attribute_not_exists(#version)",
            ExpressionAttributeNames={f"#{k}": k for k in campos},
            ExpressionAttributeValues=util.a_dynamo({**{f":{k}": x for k, x in campos.items()}, **({":v0": v} if v else {})}),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        time.sleep(random.uniform(0, 0.01))  # desfasa a los competidores
        actual = obtener(cid)
        col.clear()
        col.update(actual)
        return False
    col.update(campos)
    return True


def _etiquetar_y_registrar(col: dict, incidencia: dict, notificar_estado: bool) -> bool:
    """Marca la incidencia como parte del colectivo (condicional: solo la primera vez), deja el historial y avisa.
    Devuelve True si fue la primera vez."""
    cid = col["incidenteColectivoId"]
    try:
        db.tabla("incidencias").update_item(
            Key={"incidenciaId": incidencia["incidenciaId"]}, UpdateExpression="SET incidenteColectivoId = :c",
            ConditionExpression="attribute_exists(incidenciaId) AND attribute_not_exists(incidenteColectivoId)",
            ExpressionAttributeValues={":c": cid})
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
    historial.registrar(incidencia["incidenciaId"], "INCIDENCIA", "AGRUPADO", "SISTEMA",
                        detalle=f"Agrupada en el incidente colectivo {cid}", token=f"agrupado-{cid[-8:]}")
    # Quien se suma a un colectivo ya en marcha recibe de inmediato el aviso del estado actual.
    if notificar_estado and col.get("estado") in notificador.MENSAJES:
        notificador.notificar(incidencia, col["estado"], cid)
    return True


def _anexar_unico(colectivo_id: str, valores: dict) -> bool:
    """Añade cada valor a su lista del colectivo con UN update atómico (`list_append`), solo si ninguna de las listas
    lo contiene ya. No lee antes, así que no hay lectura-modificación-escritura que se pise: dos detectores que anexan
    incidencias distintas nunca entran en conflicto, y repetir el mismo valor es inofensivo. False si ya estaba."""
    nombres = {f"#c{n}": campo for n, campo in enumerate(valores)}
    try:
        db.tabla("colectivos").update_item(
            Key={"incidenteColectivoId": colectivo_id},
            UpdateExpression="SET " + ", ".join(f"#c{n} = list_append(if_not_exists(#c{n}, :vacia), :v{n})" for n in range(len(valores))),
            ConditionExpression=" AND ".join(f"(attribute_not_exists(#c{n}) OR NOT contains(#c{n}, :x{n}))" for n in range(len(valores))),
            ExpressionAttributeNames=nombres,
            ExpressionAttributeValues={":vacia": [], **{f":v{n}": [v] for n, v in enumerate(valores.values())},
                                       **{f":x{n}": v for n, v in enumerate(valores.values())}})
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        return False


def _ajustar_cabecera(col: dict, incidencia: dict) -> None:
    """`primerReporteEn` = el más antiguo (condicional) y, si el colectivo nació por métricas, pasa a AMBOS."""
    cid, t = col["incidenteColectivoId"], db.tabla("colectivos")
    creada = incidencia["creadaEn"]
    if not col.get("primerReporteEn") or creada < col["primerReporteEn"]:
        try:
            t.update_item(Key={"incidenteColectivoId": cid}, UpdateExpression="SET primerReporteEn = :p",
                          ConditionExpression="attribute_not_exists(primerReporteEn) OR attribute_type(primerReporteEn, :nul) "
                                              "OR primerReporteEn > :p",
                          ExpressionAttributeValues={":p": creada, ":nul": "NULL"})
            col["primerReporteEn"] = creada
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
    if col.get("origen") == "METRICAS_ANTENA":
        try:
            t.update_item(Key={"incidenteColectivoId": cid}, UpdateExpression="SET origen = :a",
                          ConditionExpression="origen = :m", ExpressionAttributeValues={":a": "AMBOS", ":m": "METRICAS_ANTENA"})
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
        col["origen"] = "AMBOS"


def agrupar_incidencias(col: dict, incidencias: list, notificar_estado: bool) -> int:
    """Suma incidencias (y sus usuarios) al colectivo sin perder escrituras concurrentes. Devuelve cuántas eran nuevas
    en la lista del colectivo. Idempotente: reintentar no duplica la lista, el historial ni los avisos.

    Caso común (incidencia y usuario nuevos): UN update atómico. Si ya estaba la incidencia, el usuario, o ambos
    (reintento, o el mismo usuario con otro reporte), se anexa por separado lo que falte: así también se repara un
    fallo a medias entre las dos listas."""
    cid, nuevas = col["incidenteColectivoId"], 0
    for i in incidencias:
        iid, uid = i["incidenciaId"], i["usuarioId"]
        # Solo se escribe lo que la copia leída no tiene (si está desfasada, el append condicional lo resuelve igual).
        faltan = {}
        if iid not in col.get("incidencias", []):
            faltan["incidencias"] = iid
        if uid not in col.get("usuariosAfectados", []):
            faltan["usuariosAfectados"] = uid
        es_nueva = False
        if faltan and _anexar_unico(cid, faltan):
            es_nueva = "incidencias" in faltan
        elif faltan:  # alguien ya había anexado alguno: se anexa por separado lo que falte
            for campo, valor in faltan.items():
                anexado = _anexar_unico(cid, {campo: valor})
                es_nueva = es_nueva or (campo == "incidencias" and anexado)
        if es_nueva:
            nuevas += 1
            col.setdefault("incidencias", []).append(iid)
            if uid not in col.setdefault("usuariosAfectados", []):
                col["usuariosAfectados"].append(uid)
        _ajustar_cabecera(col, i)
        _etiquetar_y_registrar(col, i, notificar_estado)  # idempotente: cubre también un fallo a medias anterior
    return nuevas


def agregar_antenas(col: dict, antenas: list) -> None:
    nuevas = []
    for _ in range(INTENTOS_VERSION):
        actuales = {a["antenaId"]: a for a in col.get("antenasEnFalla", [])}
        nuevas = [a for a in antenas if a["antenaId"] not in actuales]
        if not nuevas:
            return
        cambios = {"antenasEnFalla": list(actuales.values()) + nuevas}
        if col.get("usuariosAfectados") and col.get("origen") == "REPORTES_USUARIOS":
            cambios["origen"] = "AMBOS"
        falla_en = min(a.get("desde") or util.ahora_iso() for a in nuevas)
        if not col.get("primeraFallaEn") or falla_en < col["primeraFallaEn"]:
            cambios["primeraFallaEn"] = falla_en
        if _escribir_con_version(col, cambios):
            break
    else:
        raise RuntimeError(f"Conflicto de versión al agregar antenas en {col['incidenteColectivoId']}: se reintentará")
    for a in nuevas:
        _comentar_antena(col["incidenteColectivoId"], a)


def _comentar_antena(colectivo_id: str, antena: dict) -> None:
    try:
        historial.registrar(colectivo_id, "INCIDENTE_COLECTIVO", "COMENTARIO", "SISTEMA",
                            detalle=f"Antena {antena['antenaId']} en estado {antena['estado']}",
                            token=f"antena-{antena['antenaId']}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


# ---------------- Creación atómica y arranque idempotente de la Step Function ----------------
def _colectivo_nuevo(colectivo_id: str, zona_id: str, origen: str, detalle: str, incidencias: list, antenas: list,
                     simulado: bool = False) -> dict:
    ahora = util.ahora_iso()
    acelerada = _simulacion_acelerada()
    por_id = {i["incidenciaId"]: i for i in incidencias}
    antenas = list({a["antenaId"]: a for a in antenas}.values())
    if (origen == "REPORTES_USUARIOS" and antenas) or (origen == "METRICAS_ANTENA" and por_id):
        origen = "AMBOS"
    return {
        "incidenteColectivoId": colectivo_id, "zonaId": zona_id, "origen": origen, "origenDetalle": detalle,
        "detectadoEn": ahora, "actualizadoEn": ahora, "resueltoEn": None,
        "estado": "EN_EVALUACION", "pasoActual": "DETECTADO",
        "usuariosAfectados": sorted({i["usuarioId"] for i in por_id.values()}), "incidencias": list(por_id),
        "antenasEnFalla": antenas,
        "primerReporteEn": min((i["creadaEn"] for i in por_id.values()), default=None),
        "primeraFallaEn": min((a.get("desde") or ahora for a in antenas), default=None),
        "prioridad": "BAJA", "puntajePrioridad": 0, "notificacionesEnviadas": 0,
        "restablecimientoSolicitado": False, "version": 1,
        # Simulación acelerada: el tiempo activo cuenta x60 para la prioridad (escala en segundos, no en horas).
        **({"factorTiempo": escenarios.FACTOR_TIEMPO_ACELERADA} if acelerada else {}),
        # Colectivo de simulación: se ve y funciona igual, pero se etiqueta y no cuenta en lo operativo.
        **({"simulado": True} if simulado else {}),
    }


def crear(zona_id: str, origen: str, detalle: str, incidencias: list, antenas: list, consumidos: dict | None = None,
          simulado: bool = False) -> str:
    """Crea el colectivo de la zona (o se suma al que ya esté abierto) y garantiza que la Step Function arranque.

    `consumidos`: entradas de la ventana que este colectivo absorbe (se quitan de ella al terminar).
    `simulado`: el colectivo nace de datos simulados; usa su propio candado y ventana (ver cabecera del módulo).
    """
    incidencias = list({i["incidenciaId"]: i for i in incidencias}.values())  # una transacción no admite ítems repetidos
    for _ in range(3):
        abierto = colectivo_abierto(zona_id, simulado)
        if abierto:
            return unir(abierto, incidencias, antenas)
        colectivo_id = util.nuevo_id("COL")
        col = _colectivo_nuevo(colectivo_id, zona_id, origen, detalle, incidencias, antenas, simulado)
        ahora = int(time.time())
        en_tx = list(incidencias)[:MAX_INCIDENCIAS_EN_TRANSACCION]
        operaciones = [
            ("Put", "dedup", {
                "Item": {"clave": _clave_lock(zona_id, simulado), "incidenciaId": colectivo_id, "expiraEn": ahora + LOCK_DIAS * 86400},
                "ConditionExpression": "attribute_not_exists(clave) OR expiraEn < :ahora",
                "ExpressionAttributeValues": {":ahora": ahora}}),
            ("Put", "colectivos", {"Item": util.a_dynamo(col), "ConditionExpression": "attribute_not_exists(incidenteColectivoId)"}),
            ("Put", "historial", {"Item": historial.evento(
                colectivo_id, "INCIDENTE_COLECTIVO", "CREADO", "SISTEMA", detalle=detalle, estado_nuevo="EN_EVALUACION",
                ocurrido_en=col["detectadoEn"], token="creado")}),
        ]
        for i in en_tx:
            operaciones.append(("Update", "incidencias", {
                "Key": {"incidenciaId": i["incidenciaId"]}, "UpdateExpression": "SET incidenteColectivoId = :c",
                "ConditionExpression": "attribute_exists(incidenciaId)", "ExpressionAttributeValues": {":c": colectivo_id}}))
            operaciones.append(("Put", "historial", {"Item": historial.evento(
                i["incidenciaId"], "INCIDENCIA", "AGRUPADO", "SISTEMA",
                detalle=f"Agrupada en el incidente colectivo {colectivo_id}", token=f"agrupado-{colectivo_id[-8:]}")}))
        try:
            db.transaccion(operaciones)
        except ClientError as e:
            if not db.es_transaccion_cancelada(e):
                raise
            if db.motivos_cancelacion(e)[:1] == ["ConditionalCheckFailed"]:
                continue  # otro detector tomó el candado primero: volver a mirar y sumarse a su colectivo
            raise  # throttling / conflicto transitorio: el stream reintenta la invocación
        for i in incidencias[MAX_INCIDENCIAS_EN_TRANSACCION:]:
            _etiquetar_y_registrar(col, i, notificar_estado=False)  # la SFN avisa a todos en su primer paso
        for a in col["antenasEnFalla"]:
            _comentar_antena(colectivo_id, a)
        quitar_de_ventana(zona_id, consumidos, simulado)
        asegurar_ejecucion(col)
        return colectivo_id
    raise RuntimeError(f"No se pudo crear ni unirse al colectivo de {zona_id}: se reintentará")


def unir(colectivo_id: str, incidencias: list, antenas: list) -> str:
    """Suma incidencias/antenas a un colectivo abierto y se asegura de que su Step Function esté en marcha."""
    col = obtener(colectivo_id)
    agrupar_incidencias(col, incidencias, notificar_estado=True)
    agregar_antenas(col, antenas)
    asegurar_ejecucion(col)
    return colectivo_id


def _arn_ejecucion(colectivo_id: str) -> str:
    return os.environ["MAQUINA_COLECTIVO"].replace(":stateMachine:", ":execution:") + f":{colectivo_id}"


def asegurar_ejecucion(col: dict) -> str:
    """Arranca la Step Function del colectivo si aún no se hizo. `name=<colectivoId>` la hace idempotente: reintentar (o
    que dos detectores lo intenten a la vez) no crea una segunda ejecución. Cura al colectivo zombi."""
    if col.get("ejecucionArn"):
        return col["ejecucionArn"]
    cid = col["incidenteColectivoId"]
    cfg = _reglas_colectivo()
    espera = int(cfg.get("esperaVerificacionSegundos", 30))
    if col.get("factorTiempo"):  # creado durante la simulación acelerada: monitoreo cada pocos segundos
        espera = min(espera, ESPERA_ACELERADA_S)
    try:
        arn = _sfn.start_execution(
            stateMachineArn=os.environ["MAQUINA_COLECTIVO"], name=cid,
            input=json.dumps({"colectivoId": cid, "esperaSegundos": espera,
                              "monitoreo": {"iteracion": 0}}),
        )["executionArn"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "ExecutionAlreadyExists":
            raise
        arn = _arn_ejecucion(cid)  # ya estaba arrancada con otra entrada: es la misma ejecución
    actualizar(cid, ejecucionArn=arn)
    col["ejecucionArn"] = arn
    return arn


ESPERA_ACELERADA_S = 8  # monitoreo cada 8 s en la simulación acelerada (normal: 30 s); D14: el motor tiene tope 2


def _simulacion_acelerada() -> bool:
    from telecorp import config
    try:
        e = config.leer("escenario", usar_cache=False)
    except Exception:  # noqa: BLE001 - sin el parámetro, flujo normal
        return False
    return bool(e.get("activo") and e.get("tipo") == "ACELERADA")


def _reglas_colectivo() -> dict:
    from telecorp import config
    return config.leer("reglas").get("colectivo", {})
