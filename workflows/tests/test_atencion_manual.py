"""Seguimiento de los incidentes colectivos que quedaron en REQUIERE_ATENCION (el flujo automático se detuvo).

Antes el operador los veía en la lista pero no podía cerrarlos (`restablecer` respondía 409 «no está abierto») y la zona
quedaba sin dueño. Ahora `restablecer` los retoma: vuelve a reservar la zona, deja el colectivo en su estado anterior con el
restablecimiento solicitado y arranca una ejecución `reanudar` que lo cierra por el flujo normal (avisos, incidencias
solucionadas, historial, candado). Cada paso es reversible.
"""
import json

import pytest

from telecorp import util

from conftest import colectivos, historial_de, insertar, item_incidencia, tabla

OPERADOR = {"sub": "op-0001-abcd", "cognito:groups": "[operadores]"}
CIUDADANO = {"sub": "usr-0002-efgh", "cognito:groups": "[otros]"}


def _evento(cid, claims=OPERADOR):
    return {"pathParameters": {"colectivoId": cid},
            "requestContext": {"authorizer": {"jwt": {"claims": claims}}}}


@pytest.fixture()
def api(aws, monkeypatch):
    import colectivos as api_colectivos
    monkeypatch.setenv("MAQUINA_COLECTIVO", "arn:aws:states:us-east-1:123456789012:stateMachine:test")
    sfn = type("S", (), {})()
    sfn.llamadas, sfn.fallar = [], False

    def start_execution(**kw):
        if sfn.fallar:
            raise RuntimeError("StartExecution caído (simulado)")
        sfn.llamadas.append(kw)
        return {"executionArn": f"arn:aws:states:us-east-1:123456789012:execution:test:{kw['name']}"}

    sfn.start_execution = start_execution
    monkeypatch.setattr(api_colectivos, "_sfn", sfn)
    api_colectivos.sfn_falso = sfn
    return api_colectivos


def _requiere_atencion(cid="COL-ATN", zona="ZONA-05", simulado=False, previo="INCIDENCIA_CONFIRMADA", n=3):
    incidencias = [insertar(item_incidencia(f"7100{i:04d}", zona=zona, estado="EN_ATENCION")) for i in range(n)]
    ahora = util.ahora_iso()
    item = {"incidenteColectivoId": cid, "zonaId": zona, "estado": "REQUIERE_ATENCION", "pasoActual": "ATENCION_MANUAL",
            "estadoAntesDeAtencion": previo, "detectadoEn": ahora, "actualizadoEn": ahora, "origen": "REPORTES_USUARIOS",
            "usuariosAfectados": [i["usuarioId"] for i in incidencias], "incidencias": [i["incidenciaId"] for i in incidencias],
            "ejecucionArn": "arn:viejo", "restablecimientoSolicitado": False, "prioridad": "ALTA", "puntajePrioridad": 7}
    if simulado:
        item["simulado"] = True
    tabla("colectivos").put_item(Item=util.a_dynamo(item))
    return item


def _lock(zona="ZONA-05", sim=False):
    import comun_colectivos as cc
    return tabla("dedup").get_item(Key={"clave": cc._clave_lock(zona, sim)}).get("Item")


def test_la_clave_del_candado_coincide_con_la_del_detector(api):
    import comun_colectivos as cc
    for zona in ("ZONA-05", "ZONA-01"):
        for sim in (False, True):
            assert api._clave_candado(zona, sim) == cc._clave_lock(zona, sim)


def test_el_operador_retoma_un_incidente_en_atencion_manual(api):
    _requiere_atencion()
    r = api.restablecer(_evento("COL-ATN"), None)
    assert r["statusCode"] == 200 and json.loads(r["body"])["retomado"] is True
    col = tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-ATN"})["Item"]
    assert col["estado"] == "INCIDENCIA_CONFIRMADA" and col["restablecimientoSolicitado"] is True
    assert col["ejecucionArn"] != "arn:viejo"                                    # una ejecución nueva, no la caída
    (llamada,) = api.sfn_falso.llamadas
    entrada = json.loads(llamada["input"])
    assert entrada["reanudar"] is True and entrada["colectivoId"] == "COL-ATN" and llamada["name"].startswith("COL-ATN-a")
    assert _lock()["incidenciaId"] == "COL-ATN"                                  # la zona vuelve a tener dueño
    ev = [e for e in historial_de("COL-ATN") if e["tipoEvento"] == "CAMBIO_ESTADO"]
    assert ev and ev[0]["estadoAnterior"] == "REQUIERE_ATENCION" and ev[0]["actor"] == "operador:op-0001-abcd"


def test_sin_estado_previo_guardado_vuelve_a_evaluacion(api):
    _requiere_atencion(previo=None)
    api.restablecer(_evento("COL-ATN"), None)
    assert tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-ATN"})["Item"]["estado"] == "EN_EVALUACION"


def test_si_la_zona_ya_tiene_otro_incidente_abierto_responde_409_y_no_cambia_nada(api):
    import comun_colectivos as cc
    _requiere_atencion()
    ahora = util.ahora_iso()
    tabla("colectivos").put_item(Item=util.a_dynamo({"incidenteColectivoId": "COL-OTRO", "zonaId": "ZONA-05",
                                                     "estado": "EN_EVALUACION", "detectadoEn": ahora}))
    assert cc.tomar_lock("ZONA-05", "COL-OTRO") is None
    r = api.restablecer(_evento("COL-ATN"), None)
    assert r["statusCode"] == 409 and "COL-OTRO" in json.loads(r["body"])["error"]
    assert tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-ATN"})["Item"]["estado"] == "REQUIERE_ATENCION"
    assert _lock()["incidenciaId"] == "COL-OTRO" and api.sfn_falso.llamadas == []


def test_un_candado_huerfano_no_impide_retomar(api):
    import comun_colectivos as cc
    _requiere_atencion()
    assert cc.tomar_lock("ZONA-05", "COL-FANTASMA") is None                      # su colectivo no existe
    assert api.restablecer(_evento("COL-ATN"), None)["statusCode"] == 200
    assert _lock()["incidenciaId"] == "COL-ATN"


def test_si_falla_step_functions_se_deshace_todo(api):
    _requiere_atencion()
    api.sfn_falso.fallar = True
    r = api.restablecer(_evento("COL-ATN"), None)
    assert r["statusCode"] == 502
    col = tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-ATN"})["Item"]
    assert col["estado"] == "REQUIERE_ATENCION" and col["restablecimientoSolicitado"] is False
    assert _lock() is None                                                       # la zona queda libre para otros
    api.sfn_falso.fallar = False
    assert api.restablecer(_evento("COL-ATN"), None)["statusCode"] == 200        # y se puede reintentar


def test_un_incidente_cerrado_o_inexistente_sigue_dando_409(api):
    ahora = util.ahora_iso()
    tabla("colectivos").put_item(Item=util.a_dynamo({"incidenteColectivoId": "COL-CERRADO", "zonaId": "ZONA-05",
                                                     "estado": "CERRADO", "detectadoEn": ahora}))
    assert api.restablecer(_evento("COL-CERRADO"), None)["statusCode"] == 409
    assert api.restablecer(_evento("COL-NO-EXISTE"), None)["statusCode"] == 409


def test_solo_un_operador_puede_retomar(api):
    _requiere_atencion()
    assert api.restablecer(_evento("COL-ATN", CIUDADANO), None)["statusCode"] == 403
    assert api.sfn_falso.llamadas == []


def test_un_colectivo_simulado_reserva_su_propio_candado(api):
    _requiere_atencion(simulado=True)
    assert api.restablecer(_evento("COL-ATN"), None)["statusCode"] == 200
    assert _lock(sim=True)["incidenciaId"] == "COL-ATN" and _lock() is None


def test_el_flujo_normal_lo_cierra_y_libera_la_zona(api, monkeypatch):
    """Tras retomarlo, `reverificar` obedece al operador y `restablecer` + `cerrar` hacen el cierre de siempre."""
    import pasos
    monkeypatch.setattr(pasos.notificador, "notificar", lambda *a, **k: None)
    monkeypatch.setattr(pasos, "_refrescar_analisis", lambda col: False)
    _requiere_atencion()
    api.restablecer(_evento("COL-ATN"), None)
    r = pasos.reverificar({"colectivoId": "COL-ATN", "iteracion": 0}, None)
    assert r["restablecido"] is True and r["via"] == "OPERADOR"
    pasos.restablecer({"colectivoId": "COL-ATN", "via": "OPERADOR"}, None)
    pasos.cerrar({"colectivoId": "COL-ATN"}, None)
    col = tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-ATN"})["Item"]
    assert col["estado"] == "CERRADO" and col.get("resueltoEn")
    assert _lock() is None                                                       # candado liberado
    estados = {i["estado"] for i in tabla("incidencias").scan()["Items"]}
    assert estados == {"SOLUCIONADA"}                                            # las incidencias se solucionan


def test_el_flujo_recuerda_el_estado_previo_al_pasar_a_atencion_manual(api):
    import comun_colectivos as cc
    import pasos
    ahora = util.ahora_iso()
    tabla("colectivos").put_item(Item=util.a_dynamo({"incidenteColectivoId": "COL-X", "zonaId": "ZONA-05",
                                                     "estado": "INCIDENCIA_CONFIRMADA", "detectadoEn": ahora}))
    cc.tomar_lock("ZONA-05", "COL-X")
    pasos.sin_resolver({"colectivoId": "COL-X"}, None)
    col = tabla("colectivos").get_item(Key={"incidenteColectivoId": "COL-X"})["Item"]
    assert col["estado"] == "REQUIERE_ATENCION" and col["estadoAntesDeAtencion"] == "INCIDENCIA_CONFIRMADA"
    assert _lock() is None
    assert [c["estado"] for c in colectivos()] == ["REQUIERE_ATENCION"]
