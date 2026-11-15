"""Separación de datos SIMULADOS y OPERATIVOS: detector, estadísticas, analítica, recurrencia y estado público.

Regla de diseño (ver `reglas.es_simulado` y la cabecera de `comun_colectivos`): lo simulado (Tormenta, fallas forzadas del
simulador, vecinos ficticios) y lo operativo viven en universos separados: cada uno cuenta sus propios usuarios, tiene su propio
candado por zona y su propia serie de contadores. Nada se borra: los datos simulados siguen consultables, pero aparte.
"""
from datetime import timedelta

import pytest

from telecorp import config, estadisticas, reglas, util

from conftest import colectivos, historial_de, insertar, item_incidencia, tabla


def hace(**delta):
    return util.iso(util.ahora() - timedelta(**delta))


def _real(i, zona="ZONA-05", **kw):
    return insertar(item_incidencia(f"8100{i:04d}", zona=zona, **{"creada": hace(minutes=i + 1), **kw}))


def _simulada(i, zona="ZONA-05", **kw):
    inc = item_incidencia(f"9100{i:04d}", zona=zona, **{"creada": hace(minutes=i + 1), **kw})
    inc["reporte"]["simulado"] = True
    return insertar(inc)


# ======================= Criterio único =======================
def test_es_simulado_reconoce_cada_forma_y_no_confunde_lo_operativo():
    assert reglas.es_simulado({"reporte": {"simulado": True}})          # incidencia
    assert reglas.es_simulado({"simulado": True})                        # colectivo / evento de historial
    assert reglas.es_simulado({"simulada": True})                        # antena (falla forzada)
    assert not reglas.es_simulado({"reporte": {"tipo": "SIN_INTERNET"}})
    assert not reglas.es_simulado({"simulado": False, "simulada": False})
    assert not reglas.es_simulado(None) and not reglas.es_simulado({})


def test_el_usuario_no_puede_declarar_su_reporte_como_simulado():
    """`construir_reporte` solo toma tipo/descripción/ubicación: un campo `simulado` enviado por el cliente se descarta."""
    r = reglas.construir_reporte({"tipo": "SIN_INTERNET", "descripcion": "x", "simulado": True},
                                 {"dni": "70000001", "zonaId": "ZONA-05"}, None, util.ahora_iso())
    assert "simulado" not in r and not reglas.es_simulado({"reporte": r})


def test_contar_fallas_separa_los_dos_universos():
    desde = "2026-01-01T00:00:00Z"

    def ev(t, sim=False):
        e = {"tipoEvento": "CAMBIO_ESTADO", "ocurridoEn": t, "estadoAnterior": "NORMAL", "estadoNuevo": "CAIDA"}
        return {**e, "simulado": True} if sim else e

    eventos = [ev("2026-02-01T00:00:00Z"), ev("2026-02-02T00:00:00Z", True), ev("2026-02-03T00:00:00Z", True)]
    assert reglas.contar_fallas(eventos, desde) == 1
    assert reglas.contar_fallas(eventos, desde, simulados=True) == 2


# ======================= Detector: dos universos, dos candados =======================
def test_nueve_reales_mas_uno_simulado_no_forman_colectivo(aws):
    import detector
    for i in range(9):
        detector.nueva_incidencia(_real(i))
    detector.nueva_incidencia(_simulada(0))
    assert colectivos() == []           # 9 reales + 1 simulado ≠ 10 usuarios reales
    detector.nueva_incidencia(_real(9))  # el 10.º real sí lo completa
    (col,) = colectivos()
    assert len(col["usuariosAfectados"]) == 10 and not col.get("simulado")
    assert all(not u.startswith("9100") for u in col["usuariosAfectados"])


def test_una_tormenta_crea_su_colectivo_simulado_y_no_bloquea_la_zona_real(aws):
    import comun_colectivos as cc
    import detector
    for i in range(10):
        detector.nueva_incidencia(_simulada(i))
    (sim,) = colectivos()
    assert sim["simulado"] is True and sim["origen"] == "REPORTES_USUARIOS"
    assert cc.colectivo_abierto("ZONA-05", sim=True) == sim["incidenteColectivoId"]
    assert cc.colectivo_abierto("ZONA-05") is None                      # la zona REAL sigue libre
    for i in range(10):
        detector.nueva_incidencia(_real(i))                              # diez usuarios reales en la misma zona
    cols = colectivos()
    assert len(cols) == 2
    real = next(c for c in cols if not c.get("simulado"))
    assert cc.colectivo_abierto("ZONA-05") == real["incidenteColectivoId"]
    assert set(real["usuariosAfectados"]).isdisjoint(sim["usuariosAfectados"])   # nadie se mezcla


def test_un_reporte_simulado_no_se_suma_al_colectivo_real_abierto(aws):
    import detector
    for i in range(10):
        detector.nueva_incidencia(_real(i))
    (real,) = colectivos()
    detector.nueva_incidencia(_simulada(50))
    (real,) = [c for c in colectivos() if not c.get("simulado")]
    assert len(real["usuariosAfectados"]) == 10                          # no creció con el simulado
    simulado = [i for i in tabla("incidencias").scan()["Items"] if reglas.es_simulado(i)]
    assert len(simulado) == 1 and not simulado[0].get("incidenteColectivoId")   # existe, pero sin agrupar


def test_falla_forzada_de_antena_crea_colectivo_simulado_y_la_real_uno_operativo(aws):
    import comun_colectivos as cc
    import detector
    base = {"antenaId": "ANT-013", "zonaId": "ZONA-05", "estado": "INHABILITADA", "estadoDesde": util.ahora_iso()}
    detector.cambio_antena({"estado": "NORMAL"}, {**base, "simulada": True})
    (sim,) = colectivos()
    assert sim["simulado"] is True and sim["origen"] == "METRICAS_ANTENA"
    assert cc.colectivo_abierto("ZONA-05") is None
    detector.cambio_antena({"estado": "NORMAL"}, {**base, "antenaId": "ANT-014"})   # sin marca: una antena real
    assert len(colectivos()) == 2 and any(not c.get("simulado") for c in colectivos())


def test_reconciliar_evalua_cada_universo_por_separado(aws):
    import detector
    for i in range(10):
        _simulada(i)                    # sin pasar por el stream: lo debe encontrar el barrido
    for i in range(3):
        _real(i)
    detector.reconciliar({}, None)
    (col,) = colectivos()
    assert col["simulado"] is True and len(col["usuariosAfectados"]) == 10


def test_cerrar_un_colectivo_simulado_libera_solo_su_candado(aws):
    import comun_colectivos as cc
    assert cc.tomar_lock("ZONA-05", "COL-REAL") is None
    assert cc.tomar_lock("ZONA-05", "COL-SIM", sim=True) is None
    cc.liberar_lock("ZONA-05", "COL-SIM", sim=True)
    item = tabla("dedup").get_item(Key={"clave": cc._clave_lock("ZONA-05")}).get("Item")
    assert item and item["incidenciaId"] == "COL-REAL"                    # el candado real sigue intacto


# ======================= Antenas: la marca viaja del simulador al historial =======================
def test_clasificador_propaga_la_marca_a_la_antena_y_a_su_historial(aws):
    import clasificador
    ahora = util.ahora()
    t0, t1, t2 = (util.iso(ahora - timedelta(minutes=m)) for m in (3, 2, 1))
    clasificador.procesar({"antenaId": "ANT-013", "zonaId": "ZONA-05", "medidoEn": t0, "gbPorMinuto": 90.0})
    clasificador.procesar({"antenaId": "ANT-013", "zonaId": "ZONA-05", "medidoEn": t1, "gbPorMinuto": 0.0, "simulada": True})
    antena = tabla("antenas").get_item(Key={"antenaId": "ANT-013"})["Item"]
    assert antena["estado"] == "INHABILITADA" and antena["simulada"] is True
    cambios = [e for e in historial_de("ANT-013") if e["tipoEvento"] == "CAMBIO_ESTADO"]
    assert [bool(e.get("simulado")) for e in sorted(cambios, key=lambda e: e["ocurridoEn"])] == [False, True]
    # Al volver a la normalidad con una lectura natural, la antena deja de estar marcada.
    clasificador.procesar({"antenaId": "ANT-013", "zonaId": "ZONA-05", "medidoEn": t2, "gbPorMinuto": 88.0})
    assert tabla("antenas").get_item(Key={"antenaId": "ANT-013"})["Item"]["simulada"] is False


# ======================= Estadísticas y analítica =======================
def test_los_contadores_de_reportes_simulados_van_a_series_aparte():
    assert estadisticas.serie_de("GLOBAL") == "GLOBAL"
    assert estadisticas.serie_de("GLOBAL", True) == "SIM#GLOBAL"
    assert estadisticas.serie_de("ZONA-05", True) == "SIM#ZONA-05"


def _colectivo(cid, zona, simulado, afectados, estado="CERRADO"):
    ahora = util.ahora_iso()
    item = {"incidenteColectivoId": cid, "zonaId": zona, "estado": estado, "detectadoEn": ahora, "actualizadoEn": ahora,
            "usuariosAfectados": [f"u{n}" for n in range(afectados)], "incidencias": [], "origen": "REPORTES_USUARIOS",
            "prioridad": "ALTA", "puntajePrioridad": 5, "duracionMinutos": 10}
    if simulado:
        item["simulado"] = True
    tabla("colectivos").put_item(Item=util.a_dynamo(item))


def _falla(antena, simulado):
    from telecorp import historial
    historial.registrar(antena, "ANTENA", "CAMBIO_ESTADO", "SISTEMA", estado_anterior="NORMAL", estado_nuevo="CAIDA",
                        token="t" + ("s" if simulado else "r"), simulado=simulado)


def test_la_analitica_no_mezcla_universos(aws):
    import analitica
    config.escribir("recurrencia", {})
    _colectivo("COL-REAL", "ZONA-05", False, 12)
    _colectivo("COL-SIM-1", "ZONA-05", True, 40)
    _colectivo("COL-SIM-2", "ZONA-03", True, 60)
    ahora = util.ahora()
    b = estadisticas.bucket(ahora)
    for serie, n in (("GLOBAL", 3), ("SIM#GLOBAL", 500)):
        for _ in range(n):
            estadisticas.incrementar(tabla("estadisticas"), serie, b, "SIN_INTERNET", int(ahora.timestamp()) + 99999)
    _falla("ANT-013", False)
    _falla("ANT-014", True)

    op = analitica._calcular(7)
    assert op["datos"] == "OPERATIVOS"
    assert op["kpis"]["incidentes"] == 1 and op["kpis"]["afectadosTotales"] == 12 and op["kpis"]["reportes"] == 3
    assert [a["antenaId"] for a in op["antenas"]] == ["ANT-013"] and all(not i["simulado"] for i in op["incidentes"])

    sim = analitica._calcular(7, simulados=True)
    assert sim["datos"] == "SIMULADOS"
    assert sim["kpis"]["incidentes"] == 2 and sim["kpis"]["afectadosTotales"] == 100 and sim["kpis"]["reportes"] == 500
    assert [a["antenaId"] for a in sim["antenas"]] == ["ANT-014"] and all(i["simulado"] for i in sim["incidentes"])


def test_el_endpoint_de_analitica_valida_el_parametro_datos(aws):
    import analitica
    config.escribir("recurrencia", {})
    analitica._cache.clear()
    r = analitica.analitica({"queryStringParameters": {"dias": "7", "datos": "mezclados"}}, None)
    assert r["statusCode"] == 400
    r = analitica.analitica({"queryStringParameters": {"dias": "7"}}, None)
    assert r["statusCode"] == 200


# ======================= Estado público =======================
def test_el_estado_publico_ignora_lo_simulado_pero_avisa_que_hay_una_simulacion(aws):
    import estado
    _colectivo("COL-REAL", "ZONA-05", False, 12, estado="INCIDENCIA_CONFIRMADA")
    _colectivo("COL-SIM", "ZONA-03", True, 80, estado="INCIDENCIA_CONFIRMADA")
    r = estado._calcular("GLOBAL")
    assert [c["incidenteColectivoId"] for c in r["colectivos"]] == ["COL-REAL"]
    assert r["simulacion"] == {"colectivosAbiertos": 1}
    zonas = {z["zonaId"]: z["nivel"] for z in r["zonas"]}
    assert zonas["ZONA-03"] == "SIN_PROBLEMAS" and zonas["ZONA-05"] == "PROBLEMAS"


# ======================= Recurrencia =======================
def _fallas_recurrentes(antena, simulado, n=3):
    from telecorp import historial
    for k in range(n):
        historial.registrar(antena, "ANTENA", "CAMBIO_ESTADO", "SISTEMA", estado_anterior="NORMAL", estado_nuevo="CAIDA",
                            ocurrido_en=hace(hours=k + 1), token=f"f{k}", simulado=simulado)


def test_la_recurrencia_diaria_ignora_las_fallas_simuladas(aws):
    import recurrencia
    config.escribir("reglas", {"recurrencia": {"umbralFallas": 3, "ventanaDias": 7}})
    _fallas_recurrentes("ANT-013", simulado=True)
    assert recurrencia.contar({}, None)["estructurales"] == []                         # lo operativo no ve nada
    c = recurrencia.contar({"simulados": True}, None)
    assert [e["antenaId"] for e in c["estructurales"]] == ["ANT-013"] and c["estructurales"][0]["simulado"] is True


def test_marcar_una_antena_simulada_no_alerta_al_noc_y_no_se_mezcla(aws, monkeypatch):
    import recurrencia
    publicados = []
    monkeypatch.setattr(recurrencia._sns, "publish", lambda **kw: publicados.append(kw))
    monkeypatch.setenv("TOPICO_ALERTAS", "arn:aws:sns:us-east-1:123456789012:alertas")
    config.escribir("reglas", {"recurrencia": {"umbralFallas": 3, "ventanaDias": 7}})
    ev = {"antenaId": "ANT-013", "zonaId": "ZONA-05", "fallas": 3, "ventanaDias": 7}
    recurrencia.marcar({**ev, "simulado": True}, None)
    assert publicados == []                                                            # una simulación no despierta al NOC
    assert tabla("antenas").get_item(Key={"antenaId": "ANT-013"})["Item"]["estructural"]["simulado"] is True
    # La ejecución operativa no desmarca ni toca la marca simulada (no la puede juzgar)…
    recurrencia.contar({}, None)
    assert tabla("antenas").get_item(Key={"antenaId": "ANT-013"})["Item"].get("estructural")
    # …y una marca operativa sí alerta.
    recurrencia.marcar({**ev, "antenaId": "ANT-014"}, None)
    assert len(publicados) == 1


# ======================= «Reiniciar demo» solo toca lo simulado =======================
def test_reiniciar_la_demo_no_cierra_los_incidentes_de_usuarios_reales(aws, monkeypatch):
    import colectivos as api_colectivos
    import escenarios as api_escenarios
    config.escribir("escenario", {"activo": False})
    config.escribir("simulador", {"activo": True, "fallas": {"ANT-013": 0}})
    monkeypatch.setenv("FUNCION_SIMULADOR", "telecorp-test-simulador")
    monkeypatch.setattr(api_escenarios._lambda, "invoke", lambda **kw: {})
    monkeypatch.setattr(api_colectivos, "reanudar_huerfanos", lambda: [])
    _colectivo("COL-REAL", "ZONA-05", False, 12, estado="INCIDENCIA_CONFIRMADA")
    _colectivo("COL-SIM", "ZONA-03", True, 80, estado="INCIDENCIA_CONFIRMADA")
    evento = {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "op-0001-abcd", "cognito:groups": "[operadores]"}}}}}
    r = api_escenarios.reiniciar(evento, None)
    assert r["statusCode"] == 200
    real = tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-REAL"})["Item"]
    sim = tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-SIM"})["Item"]
    assert not real.get("restablecimientoSolicitado")                    # el incidente real sigue su curso
    assert sim["restablecimientoSolicitado"] is True
    assert config.leer("simulador", usar_cache=False)["fallas"] == {}    # y las fallas forzadas se quitan


# ======================= Una simulación no puede alterar un incidente REAL abierto =======================
def _evento_operador(cuerpo):
    import json
    return {"body": json.dumps(cuerpo), "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "op-0001-abcd", "cognito:groups": "[operadores]"}}}}}


@pytest.fixture()
def api_escenarios(aws, monkeypatch):
    import escenarios as api
    config.escribir("escenario", {"activo": False})
    monkeypatch.setenv("MAQUINA_ESCENARIO", "arn:aws:states:us-east-1:123456789012:stateMachine:esc")
    llamadas = []
    monkeypatch.setattr(api, "_sfn", type("S", (), {"start_execution": staticmethod(lambda **kw: llamadas.append(kw) or {"executionArn": "arn:x"})})())
    api.llamadas = llamadas
    return api


def _lanzar(api, tipo, zona):
    return api.lanzar(_evento_operador({"tipo": tipo, "zonaId": zona}), None)


def test_no_se_lanza_una_tormenta_sobre_una_zona_con_incidente_real_abierto(api_escenarios):
    _colectivo("COL-REAL", "ZONA-05", False, 12, estado="INCIDENCIA_CONFIRMADA")
    r = _lanzar(api_escenarios, "TORMENTA", "ZONA-05")
    assert r["statusCode"] == 409 and "incidente real abierto" in r["body"]
    assert api_escenarios.llamadas == []


def test_tampoco_sobre_una_zona_vecina_que_la_tormenta_tambien_forzaria(api_escenarios):
    from telecorp import escenarios as esc, zonas
    vecina = esc.zonas_afectadas("TORMENTA", "ZONA-05", zonas.zonas())[1]["zonaId"]
    _colectivo("COL-REAL", vecina, False, 12, estado="EN_EVALUACION")
    assert _lanzar(api_escenarios, "TORMENTA", "ZONA-05")["statusCode"] == 409


def test_una_zona_lejana_cerrada_o_simulada_no_bloquea(api_escenarios):
    from telecorp import escenarios as esc, zonas
    en_juego = {z["zonaId"] for z in esc.zonas_afectadas("TORMENTA", "ZONA-05", zonas.zonas())}
    lejana = next(z["zonaId"] for z in zonas.zonas() if z["zonaId"] not in en_juego)
    _colectivo("COL-LEJOS", lejana, False, 12, estado="INCIDENCIA_CONFIRMADA")   # real pero fuera de las zonas del escenario
    _colectivo("COL-CERRADO", "ZONA-05", False, 12, estado="CERRADO")             # real pero ya cerrado
    _colectivo("COL-SIM", "ZONA-05", True, 40, estado="INCIDENCIA_CONFIRMADA")    # simulado: otra simulación no lo altera
    assert _lanzar(api_escenarios, "TORMENTA", "ZONA-05")["statusCode"] == 202


def test_la_acelerada_toca_zonas_al_azar_asi_que_cualquier_incidente_real_la_bloquea(api_escenarios):
    assert _lanzar(api_escenarios, "ACELERADA", "ZONA-05")["statusCode"] == 202
    config.escribir("escenario", {"activo": False})
    _colectivo("COL-REAL", "ZONA-01", False, 12, estado="INCIDENCIA_CONFIRMADA")
    assert _lanzar(api_escenarios, "ACELERADA", "ZONA-05")["statusCode"] == 409


@pytest.fixture()
def api_simulador(aws, monkeypatch):
    import importlib.util
    import pathlib
    ruta = pathlib.Path(__file__).resolve().parents[2] / "services" / "api" / "src" / "simulador.py"
    spec = importlib.util.spec_from_file_location("api_simulador", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    config.escribir("simulador", {"fallas": {"ANT-013": 35}, "probSaturacion": 0.03})
    monkeypatch.setattr(modulo, "_schedule", lambda: {"State": "ENABLED", "Name": "x"})
    monkeypatch.setenv("FUNCION_SIMULADOR", "telecorp-test-simulador")
    monkeypatch.setattr(modulo._lambda, "invoke", lambda **kw: {})
    return modulo


def test_no_se_fuerza_una_antena_de_una_zona_con_incidente_real_abierto(api_simulador):
    _colectivo("COL-REAL", "ZONA-05", False, 12, estado="INCIDENCIA_CONFIRMADA")   # ANT-013 es de ZONA-05
    r = api_simulador.actualizar(_evento_operador({"fallas": {"ANT-013": 0}}), None)
    assert r["statusCode"] == 409 and "incidente real abierto" in r["body"]
    assert config.leer("simulador", usar_cache=False)["fallas"] == {"ANT-013": 35}   # no se tocó nada


def test_si_se_permite_restaurar_o_forzar_en_otra_zona(api_simulador):
    _colectivo("COL-REAL", "ZONA-05", False, 12, estado="INCIDENCIA_CONFIRMADA")
    assert api_simulador.actualizar(_evento_operador({"fallas": {"ANT-013": None}}), None)["statusCode"] == 200     # restaurar
    assert api_simulador.actualizar(_evento_operador({"fallas": {"ANT-001": 0}}), None)["statusCode"] == 200        # ANT-001 es de ZONA-01


def test_las_funciones_que_arrancan_step_functions_declaran_su_maquina():
    """Lección de la prueba en la nube: `restablecer` retomaba incidentes con Step Functions pero su función no tenía la variable (502)."""
    from conftest import cargar_yaml
    funciones = cargar_yaml("services/api/serverless.yml")["functions"]
    # D14: todas las rutas están en el router único `api`, que declara las máquinas que arranca.
    entorno = funciones["api"].get("environment") or {}
    for variable in ("MAQUINA_COLECTIVO", "MAQUINA_ESCENARIO", "MAQUINA_RECURRENCIA"):
        assert variable in entorno, variable
