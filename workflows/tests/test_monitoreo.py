"""Reglas puras del monitoreo del colectivo y estructura de la máquina de estados (sin AWS)."""
import pathlib

import pytest

import monitoreo

BASE = dict(solicitado=False, afectadas=[], estados={}, confirmada=False, sin_reportes_recientes=False,
            iteracion=1, max_iteraciones=2000, minutos_transcurridos=10, max_minutos=2880)


def decidir(**cambios):
    return monitoreo.decidir(**{**BASE, **cambios})


# ---------------- lotes ----------------
@pytest.mark.parametrize("total, tam, esperado", [(0, 50, 0), (1, 50, 1), (50, 50, 1), (51, 50, 2), (5000, 50, 100), (7, 0, 7)])
def test_cantidad_de_lotes(total, tam, esperado):
    assert monitoreo.cantidad_lotes(total, tam) == esperado


# ---------------- restablecimiento ----------------
def test_el_operador_manda_aunque_haya_antenas_en_falla():
    d = decidir(solicitado=True, afectadas=["A1"], estados={"A1": "CAIDA"})
    assert d == {"restablecido": True, "via": "OPERADOR", "agotado": False, "escalar": False}


def test_con_antenas_registradas_se_restablece_cuando_todas_se_normalizan():
    d = decidir(afectadas=["A1", "A2"], estados={"A1": "NORMAL", "A2": "NORMAL", "A3": "NORMAL"}, confirmada=True)
    assert d["restablecido"] and d["via"] == "AUTOMATICO"


def test_con_antenas_registradas_basta_una_en_falla_para_no_restablecer():
    d = decidir(afectadas=["A1", "A2"], estados={"A1": "NORMAL", "A2": "INHABILITADA"}, confirmada=True)
    assert not d["restablecido"] and not d["escalar"]


def test_una_antena_saturada_todavia_no_cuenta_como_restablecida():
    assert not decidir(afectadas=["A1"], estados={"A1": "SATURADA"}, confirmada=True)["restablecido"]


def test_sin_antenas_registradas_se_cierra_por_silencio_de_reportes():
    d = decidir(estados={"A1": "NORMAL"}, sin_reportes_recientes=True)
    assert d["restablecido"] and d["via"] == "SIN_REPORTES"


def test_sin_antenas_pero_con_reportes_recientes_no_se_cierra():
    assert not decidir(estados={"A1": "NORMAL"}, sin_reportes_recientes=False)["restablecido"]


def test_sin_antenas_registradas_nunca_se_cierra_por_silencio_si_hay_una_degradada_ahora():
    d = decidir(estados={"A1": "CAIDA"}, sin_reportes_recientes=True)
    assert not d["restablecido"] and d["escalar"]


# ---------------- escalada ----------------
@pytest.mark.parametrize("estado, confirmada, escalar", [("CAIDA", False, True), ("SATURADA", False, True),
                                                         ("INHABILITADA", False, True), ("CAIDA", True, False),
                                                         ("NORMAL", False, False)])
def test_escalar_solo_si_hay_antena_degradada_y_aun_no_estaba_confirmado(estado, confirmada, escalar):
    assert decidir(estados={"A1": estado}, confirmada=confirmada)["escalar"] is escalar


# ---------------- límites del monitoreo ----------------
def test_agotado_por_iteraciones_en_el_limite_exacto():
    assert not decidir(iteracion=1999)["agotado"] and decidir(iteracion=2000)["agotado"]


def test_agotado_por_tiempo_en_el_limite_exacto():
    assert not decidir(minutos_transcurridos=2879.9)["agotado"] and decidir(minutos_transcurridos=2880)["agotado"]


def test_restablecer_tiene_prioridad_sobre_agotar():
    d = decidir(estados={"A1": "NORMAL"}, sin_reportes_recientes=True, iteracion=5000, minutos_transcurridos=9999)
    assert d["restablecido"] and not d["agotado"]


# ---------------- estructura de la máquina de estados ----------------
def _asl():
    yaml = pytest.importorskip("yaml")
    ruta = pathlib.Path(__file__).resolve().parents[1] / "statemachines" / "incidente-colectivo.yml"
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def test_la_maquina_no_tiene_estados_huerfanos_ni_Choice_sin_Default():
    estados = _asl()["States"]
    visitados, pendientes = set(), [_asl()["StartAt"]]
    while pendientes:
        n = pendientes.pop()
        if n in visitados:
            continue
        visitados.add(n)
        s = estados[n]
        destinos = [s.get("Next"), s.get("Default")] + [c.get("Next") for c in s.get("Choices", [])] \
            + [c.get("Next") for c in s.get("Catch", [])]
        pendientes += [d for d in destinos if d]
        if s["Type"] == "Choice":
            assert s.get("Default"), n
    assert visitados == set(estados), set(estados) - visitados


def test_la_verificacion_decide_el_flujo_y_hay_manejo_global_de_fallos():
    asl = _asl()
    assert asl["States"]["HayFalla"]["Choices"][0]["Variable"] == "$.verificacion.hayFalla"
    assert asl.get("TimeoutSeconds")
    for n, s in asl["States"].items():
        if s["Type"] in ("Task", "Map"):
            assert s.get("Catch"), f"{n} sin Catch"
        if s["Type"] == "Task":
            assert s.get("Retry") and s.get("TimeoutSeconds"), f"{n} sin Retry/TimeoutSeconds"
        if s["Type"] == "Map":
            assert any(t.get("Catch") for t in s["ItemProcessor"]["States"].values()), f"{n}: un lote fallido aborta el Map"


def _nombres_de_estado(definicion):
    """Todos los nombres de estado de la máquina, incluidos los de ItemProcessor y Branches."""
    nombres = []
    for nombre, estado in definicion["States"].items():
        nombres.append(nombre)
        subs = [estado["ItemProcessor"]] if "ItemProcessor" in estado else estado.get("Branches", [])
        for sub in subs:
            nombres += _nombres_de_estado(sub)
    return nombres


def test_los_nombres_de_estado_son_unicos_en_toda_la_maquina():
    """Step Functions rechaza `DUPLICATE_STATE_NAME` aunque el duplicado esté dentro de un Map.

    Lo detectó la API real `validate-state-machine-definition`, no el intérprete de pruebas.
    """
    nombres = _nombres_de_estado(_asl())
    repetidos = sorted({n for n in nombres if nombres.count(n) > 1})
    assert not repetidos, f"nombres de estado repetidos: {repetidos}"


def test_los_avisos_son_por_lotes_no_por_usuario():
    """Un evento por usuario limitaba la ejecución a ~1.100 afectados (25.000 eventos)."""
    maps = [s for s in _asl()["States"].values() if s["Type"] == "Map"]
    assert maps and all(m["ItemsPath"] == "$.aviso.lotes" and m["MaxConcurrency"] <= 10 for m in maps)
