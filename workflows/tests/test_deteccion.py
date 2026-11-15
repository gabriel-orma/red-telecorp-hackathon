"""Detección de incidentes colectivos: regla de los 10 usuarios, concurrencia y recuperación (H05–H11, H14, H17, H19, H25, H27).

Cada prueba afirma el comportamiento DESEADO. Las de concurrencia lanzan hilos contra moto; moto no reproduce las garantías
de aislamiento de DynamoDB (sus operaciones no son atómicas entre hilos), por lo que estas pruebas demuestran la LÓGICA bajo
entrelazados agresivos (switchinterval mínimo), no la atomicidad del servicio real: esa descansa en las condiciones de
DynamoDB (`ConditionExpression`, `TransactWriteItems`, `ReturnValues=ALL_NEW`), documentadas por AWS.
"""
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from telecorp import util

from conftest import cargar_yaml, colectivos, historial_de, insertar, item_incidencia, tabla

AHORA = datetime(2026, 11, 14, 12, 0, 0, tzinfo=timezone.utc)


def hace(**delta):
    return util.iso(util.ahora() - timedelta(**delta))


def _usuario(i):
    return f"7000{i:04d}"


def _reporte(i, **kw):
    return insertar(item_incidencia(_usuario(i), **{"creada": hace(minutes=i + 1), **kw}))


@pytest.fixture()
def reloj(monkeypatch):
    monkeypatch.setattr(util, "ahora", lambda: AHORA)


@pytest.fixture()
def hilos_agresivos(aws, monkeypatch):
    """Modelo de concurrencia fiel a DynamoDB: cada LLAMADA a la API es atómica (se serializa con un cerrojo, porque moto no
    es seguro entre hilos) y los hilos se entrelazan al máximo ENTRE llamadas, que es donde ocurren las carreras reales
    (leer-modificar-escribir, comprobar-luego-crear, etc.)."""
    import botocore.client
    cerrojo, original = threading.RLock(), botocore.client.BaseClient._make_api_call

    def llamada_atomica(self, operation_name, api_params):
        with cerrojo:
            return original(self, operation_name, api_params)

    monkeypatch.setattr(botocore.client.BaseClient, "_make_api_call", llamada_atomica)
    anterior = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    yield
    sys.setswitchinterval(anterior)


def en_paralelo(funciones):
    barrera = threading.Barrier(len(funciones))

    def correr(f):
        barrera.wait()
        return f()

    with ThreadPoolExecutor(max_workers=len(funciones)) as ex:
        return [fut.result() for fut in [ex.submit(correr, f) for f in funciones]]  # re-lanza cualquier excepción


# ======================= Regla de los 10 usuarios =======================
def test_nueve_no_diez_si_crea_un_colectivo_completo(aws):
    import detector
    for i in range(9):
        detector.nueva_incidencia(_reporte(i))
    assert colectivos() == [] and aws.llamadas == []
    detector.nueva_incidencia(_reporte(9))
    (col,) = colectivos()
    cid = col["incidenteColectivoId"]
    assert len(col["usuariosAfectados"]) == 10 and len(col["incidencias"]) == 10 and col["origen"] == "REPORTES_USUARIOS"
    assert aws.nombres == {cid} and col["ejecucionArn"].endswith(cid)            # Step Function arrancada con name=colectivoId
    assert [e["tipoEvento"] for e in historial_de(cid)] == ["CREADO"]
    for iid in col["incidencias"]:                                                # etiqueta + historial en la misma transacción
        assert tabla("incidencias").get_item(Key={"incidenciaId": iid})["Item"]["incidenteColectivoId"] == cid
        assert "AGRUPADO" in [e["tipoEvento"] for e in historial_de(iid)]


def test_diez_reportes_de_un_solo_usuario_no_son_colectivo(aws):
    import detector
    for i in range(10):
        detector.nueva_incidencia(insertar(item_incidencia("70000001", creada=hace(minutes=i + 1))))
    assert colectivos() == []


def test_frontera_de_24h_es_estricta(aws, reloj):
    """'Menos de 24 horas': un reporte de hace EXACTAMENTE 24 h no cuenta; uno de 23 h 59 min 59,999 s sí."""
    import detector
    for i in range(9):
        _reporte(i, creada=util.iso(AHORA - timedelta(hours=24)))
    detector.nueva_incidencia(_reporte(99, creada=hace(seconds=1)))
    assert colectivos() == []
    for i in range(9):
        _reporte(200 + i, creada=util.iso(AHORA - timedelta(hours=23, minutes=59, seconds=59, milliseconds=999)))
    detector.nueva_incidencia(_reporte(299, creada=hace(seconds=1)))
    assert len(colectivos()) == 1


def test_incidencia_tardia_fuera_de_ventana_no_completa_la_cuenta(aws, reloj):
    """Reproceso desde la DLQ: llega una incidencia de hace 30 h; no debe contar ni anotarse en la ventana."""
    import detector
    for i in range(9):
        _reporte(i, creada=hace(hours=1, minutes=i))
    detector.nueva_incidencia(_reporte(99, creada=hace(hours=30)))
    assert colectivos() == []


def test_diez_reportes_OTRO_no_disparan_pero_si_se_suman_a_uno_abierto(aws):
    """H11: 'OTRO' es texto libre sin relación demostrada con el servicio. Un colectivo ya abierto sí lo agrupa."""
    import detector
    for i in range(10):
        detector.nueva_incidencia(_reporte(i, tipo="OTRO"))
    assert colectivos() == []
    for i in range(10, 20):
        detector.nueva_incidencia(_reporte(i))
    (col,) = colectivos()
    detector.nueva_incidencia(_reporte(50, tipo="OTRO"))
    assert _usuario(50) in tabla("colectivos").get_item(Key={"incidenteColectivoId": col["incidenteColectivoId"]})["Item"]["usuariosAfectados"]


def test_reportes_cerrados_por_el_operador_siguen_contando(aws):
    """H10: 10 usuarios reportaron en <24 h aunque el operador ya cerró 3 de sus reportes individuales."""
    import detector
    for i in range(9):
        _reporte(i, estado="CERRADA" if i < 3 else "REGISTRADA")
    detector.nueva_incidencia(_reporte(9))
    assert len(colectivos()) == 1


def test_tras_cerrar_un_colectivo_un_reporte_nuevo_no_lo_redetecta(aws):
    """Los reportes ya agrupados (aunque queden SOLUCIONADA/CERRADA) no vuelven a contar para el siguiente colectivo."""
    import detector, pasos
    for i in range(10):
        detector.nueva_incidencia(_reporte(i))
    cid = colectivos()[0]["incidenteColectivoId"]
    pasos.cerrar({"colectivoId": cid}, None)
    detector.nueva_incidencia(_reporte(77))
    assert len(colectivos()) == 1 and len(aws.llamadas) == 1


# ======================= Atomicidad y recuperación =======================
def test_lock_huerfano_se_libera_y_la_zona_vuelve_a_detectar(aws):
    import comun_colectivos as cc, detector
    assert cc.tomar_lock("ZONA-05", "COL-FANTASMA") is None            # candado sin colectivo (p. ej. de una versión anterior)
    assert cc.colectivo_abierto("ZONA-05") is None
    for i in range(10):
        detector.nueva_incidencia(_reporte(i))
    assert len(colectivos()) == 1


def test_creacion_es_todo_o_nada_no_queda_candado_ni_colectivo(aws):
    """Si algo de la transacción falla (aquí: una incidencia que no existe), no queda NADA: ni candado ni colectivo."""
    import comun_colectivos as cc
    from botocore.exceptions import ClientError
    fantasma = item_incidencia("70000001")                              # nunca se inserta
    with pytest.raises(ClientError):
        cc.crear("ZONA-05", "REPORTES_USUARIOS", "prueba", [fantasma], [])
    assert colectivos() == [] and cc.colectivo_abierto("ZONA-05") is None
    assert tabla("dedup").scan()["Items"] == []


def test_colectivo_zombi_se_cura_al_reintentar(aws):
    """Si StartExecution falla tras crear el colectivo, el reintento arranca la Step Function (una sola vez)."""
    import detector
    for i in range(9):
        detector.nueva_incidencia(_reporte(i))
    ultimo = _reporte(9)
    aws.fallar = True
    with pytest.raises(RuntimeError):
        detector.nueva_incidencia(ultimo)
    assert len(colectivos()) == 1 and "ejecucionArn" not in colectivos()[0]
    aws.fallar = False
    detector.nueva_incidencia(ultimo)                                   # reintento del stream
    assert len(aws.llamadas) == 1 and colectivos()[0]["ejecucionArn"].endswith(colectivos()[0]["incidenteColectivoId"])
    detector.nueva_incidencia(ultimo)                                   # otro reintento: no vuelve a arrancar
    assert len(aws.llamadas) == 1


def test_reconciliar_crea_colectivos_que_el_stream_no_vio_y_cura_zombis(aws):
    import detector
    for i in range(10):
        _reporte(i)                                                     # el stream nunca los procesó
    r = detector.reconciliar({}, None)
    assert len(r["creados"]) == 1 and len(colectivos()) == 1 and len(aws.llamadas) == 1
    cid = colectivos()[0]["incidenteColectivoId"]
    tabla("colectivos").update_item(Key={"incidenteColectivoId": cid}, UpdateExpression="REMOVE ejecucionArn")  # zombi
    aws.llamadas.clear()
    assert detector.reconciliar({}, None)["curados"] == [cid] and aws.nombres == {cid}


# ======================= Concurrencia (hilos) =======================
@pytest.mark.parametrize("ronda", range(3))
def test_carrera_9_10_con_GSI_rancio_el_ultimo_en_confirmar_ve_a_los_diez(aws, monkeypatch, hilos_agresivos, ronda):
    """El GSI es eventualmente consistente: aquí devuelve SIEMPRE vacío. Solo la ventana atómica puede revelar al 10.º.
    Diez detectores en paralelo, uno por usuario: exactamente UN colectivo con los diez, una sola Step Function."""
    import comun_colectivos as cc, detector
    monkeypatch.setattr(cc, "incidencias_ventana_zona", lambda z, h, s=False: [])
    its = [_reporte(i) for i in range(10)]
    en_paralelo([lambda it=it: detector.nueva_incidencia(it) for it in its])
    (col,) = colectivos()
    assert len(col["usuariosAfectados"]) == 10 and len(set(col["incidencias"])) == 10
    assert aws.nombres == {col["incidenteColectivoId"]}


@pytest.mark.parametrize("ronda", range(3))
def test_nueve_en_paralelo_no_crean_colectivo(aws, monkeypatch, hilos_agresivos, ronda):
    import comun_colectivos as cc, detector
    monkeypatch.setattr(cc, "incidencias_ventana_zona", lambda z, h, s=False: [])
    its = [_reporte(i) for i in range(9)]
    en_paralelo([lambda it=it: detector.nueva_incidencia(it) for it in its])
    assert colectivos() == [] and aws.llamadas == []


@pytest.mark.parametrize("ronda", range(2))
def test_veinticinco_reportes_simultaneos_un_solo_colectivo_con_todos(aws, hilos_agresivos, ronda):
    import detector
    its = [_reporte(i) for i in range(25)]
    en_paralelo([lambda it=it: detector.nueva_incidencia(it) for it in its])
    (col,) = colectivos()
    assert len(col["usuariosAfectados"]) == 25 and len(set(col["incidencias"])) == 25, "se perdió una actualización"
    assert aws.nombres == {col["incidenteColectivoId"]}
    sin_etiqueta = [i["incidenciaId"] for i in tabla("incidencias").scan()["Items"] if not i.get("incidenteColectivoId")]
    assert sin_etiqueta == []


@pytest.mark.parametrize("ronda", range(3))
def test_agrupar_en_paralelo_no_pierde_actualizaciones(aws, hilos_agresivos, ronda):
    """Antes: cada detector leía el colectivo, unía las listas y escribía la lista completa (gana el último)."""
    import comun_colectivos as cc, detector
    for i in range(10):
        detector.nueva_incidencia(_reporte(i))
    cid = colectivos()[0]["incidenteColectivoId"]
    nuevas = [_reporte(100 + i) for i in range(12)]
    en_paralelo([lambda it=it: cc.agrupar_incidencias(cc.obtener(cid), [it], notificar_estado=False) for it in nuevas])
    final = cc.obtener(cid)
    assert len(set(final["incidencias"])) == 22 and len(final["usuariosAfectados"]) == 22


def test_reporte_que_se_suma_a_un_colectivo_creado_por_antena_fija_primerReporteEn_y_origen(aws):
    import comun_colectivos as cc, detector
    antena = {"antenaId": "ANT-013", "estado": "CAIDA", "desde": util.ahora_iso()}
    cid = cc.crear("ZONA-05", "METRICAS_ANTENA", "Antena ANT-013 CAIDA (detección proactiva)", [], [antena])
    assert cc.obtener(cid)["primerReporteEn"] is None and cc.obtener(cid)["origen"] == "METRICAS_ANTENA"
    it = _reporte(1)
    detector.nueva_incidencia(it)
    col = cc.obtener(cid)
    assert col["primerReporteEn"] == it["creadaEn"] and col["origen"] == "AMBOS"
    assert col["usuariosAfectados"] == [it["usuarioId"]] and col["incidencias"] == [it["incidenciaId"]]
    detector.nueva_incidencia(it)                                       # reentrega del mismo evento: no duplica
    assert cc.obtener(cid)["incidencias"] == [it["incidenciaId"]]


def test_agregar_antenas_en_paralelo_no_pierde_ninguna(aws, hilos_agresivos):
    import comun_colectivos as cc, detector
    for i in range(10):
        detector.nueva_incidencia(_reporte(i))
    cid = colectivos()[0]["incidenteColectivoId"]
    antenas = [{"antenaId": f"ANT-{n:03d}", "estado": "CAIDA", "desde": util.ahora_iso()} for n in range(8)]
    en_paralelo([lambda a=a: cc.agregar_antenas(cc.obtener(cid), [a]) for a in antenas])
    assert {a["antenaId"] for a in cc.obtener(cid)["antenasEnFalla"]} == {a["antenaId"] for a in antenas}


# ======================= Antenas: una sola escritura y reintentos =======================
T0, T1, T2 = "2026-11-14T08:00:00.000Z", "2026-11-14T10:00:00.000Z", "2026-11-14T10:01:00.000Z"


def _metrica(t, gb, antena="ANT-013"):
    return {"antenaId": antena, "zonaId": "ZONA-05", "medidoEn": t, "gbPorMinuto": gb}


def test_clasificador_deja_estadoDesde_correcto_en_una_sola_escritura(aws):
    import clasificador
    clasificador.procesar(_metrica(T0, 100))
    clasificador.procesar(_metrica(T1, 0))
    a = tabla("antenas").get_item(Key={"antenaId": "ANT-013"})["Item"]
    assert a["estado"] == "INHABILITADA" and a["estadoDesde"] == T1 and a["estadoAnterior"] == "NORMAL"
    clasificador.procesar(_metrica(T2, 0))                              # sigue en falla: estadoDesde no se mueve
    assert tabla("antenas").get_item(Key={"antenaId": "ANT-013"})["Item"]["estadoDesde"] == T1


def test_clasificador_reintento_tras_caida_completa_el_historial_sin_duplicarlo(aws, monkeypatch):
    import clasificador
    from telecorp import historial
    clasificador.procesar(_metrica(T0, 100))
    real = historial.registrar
    monkeypatch.setattr(historial, "registrar", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("throttling")))
    with pytest.raises(RuntimeError):
        clasificador.procesar(_metrica(T1, 0))                          # la antena ya cambió, el historial no se escribió
    monkeypatch.setattr(historial, "registrar", real)
    clasificador.procesar(_metrica(T1, 0))                              # reintento de SQS
    clasificador.procesar(_metrica(T1, 0))                              # reentrega extra
    cambios = [e for e in historial_de("ANT-013") if e["tipoEvento"] == "CAMBIO_ESTADO" and e["estadoNuevo"] == "INHABILITADA"]
    assert len(cambios) == 1 and cambios[0]["estadoAnterior"] == "NORMAL"


def test_clasificador_ignora_lecturas_mas_viejas(aws):
    import clasificador
    clasificador.procesar(_metrica(T1, 100))
    assert "ignorada" in clasificador.procesar(_metrica(T0, 0))
    assert tabla("antenas").get_item(Key={"antenaId": "ANT-013"})["Item"]["estado"] == "NORMAL"


# ======================= Worker de reportes y deduplicación =======================
def _mensaje(usuario="70001234"):
    it = item_incidencia(usuario)
    return {"incidenciaId": it["incidenciaId"], "creadaEn": it["creadaEn"], "reporte": it["reporte"]}


def _sqs(m):
    import json
    return {"Records": [{"messageId": "m0", "body": json.dumps(m)}]}


def test_worker_crea_incidencia_historial_y_contadores_en_una_transaccion(aws, monkeypatch):
    import incidencias
    from telecorp import db
    m = _mensaje()
    real = db.transaccion
    monkeypatch.setattr(db, "transaccion", lambda ops: (_ for _ in ()).throw(RuntimeError("throttling")))
    assert incidencias.registrar(_sqs(m), None) == {"batchItemFailures": [{"itemIdentifier": "m0"}]}
    assert tabla("incidencias").scan()["Items"] == [] and tabla("estadisticas").scan()["Items"] == []   # nada a medias
    monkeypatch.setattr(db, "transaccion", real)
    for _ in range(3):                                                  # reintento + 2 reentregas
        assert incidencias.registrar(_sqs(m), None) == {"batchItemFailures": []}
    assert [e["tipoEvento"] for e in historial_de(m["incidenciaId"])] == ["CREADO"]
    assert sum(int(i["total"]) for i in tabla("estadisticas").scan()["Items"]) == 2   # GLOBAL + zona, una sola vez


def test_claves_de_dedup_candado_y_ventana_no_colisionan_con_ningun_usuario():
    import comun_colectivos as cc
    from telecorp import db
    claves_de_sistema = {cc._clave_lock("ZONA-05"), cc._clave_ventana("ZONA-05")}
    for usuario in ("COLECTIVO", "LOCK", "VENTANA", "LOCK#COLECTIVO", "VENTANA#ZONA-05"):
        assert db.clave_dedup_usuario(usuario, "ZONA-05") not in claves_de_sistema


# ======================= Infraestructura (revisión del IaC) =======================
def test_stream_de_antenas_solo_dispara_en_la_transicion_a_falla():
    funciones = cargar_yaml("workflows/serverless.yml")["functions"]
    antenas = [e["stream"] for e in funciones["detector"]["events"] if "TablaAntenasStreamArn" in e["stream"]["arn"]][0]
    patrones = antenas["filterPatterns"]
    transicion = [p for p in patrones if "OldImage" in p.get("dynamodb", {})][0]["dynamodb"]
    assert transicion["NewImage"]["estado"]["S"] == ["CAIDA", "INHABILITADA"]
    assert transicion["OldImage"]["estado"]["S"] == [{"anything-but": ["CAIDA", "INHABILITADA"]}]
    assert any(p.get("eventName") == ["INSERT"] for p in patrones)   # primera lectura de una antena


def test_hay_barrido_de_reconciliacion_cada_5_minutos_sin_costo_fijo():
    f = cargar_yaml("workflows/serverless.yml")["functions"]["reconciliador"]
    assert f["handler"] == "src/detector.reconciliar"
    assert f["events"][0]["schedule"]["rate"] == "rate(5 minutes)"


def test_colas_con_maxReceiveCount_5_y_alarma_en_cada_dlq():
    r = cargar_yaml("services/base/serverless.yml")["resources"]["Resources"]
    for q in ("ColaReportes", "ColaMetricas"):
        assert r[q]["Properties"]["RedrivePolicy"]["maxReceiveCount"] >= 5
    alarmas = {k: v["Properties"] for k, v in r.items() if v["Type"] == "AWS::CloudWatch::Alarm"}
    assert len(alarmas) >= 3
    for p in alarmas.values():
        assert p["MetricName"] == "ApproximateNumberOfMessagesVisible" and p["AlarmActions"]
