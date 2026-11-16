"""Despacho del motor único (D14): acción de Step Functions, streams o barrido programado."""
import motor


def test_accion_con_campos_directos(monkeypatch):
    visto = {}
    monkeypatch.setitem(motor.PASOS, "priorizar", lambda e, c: visto.setdefault("e", e) or "ok")
    motor.handler({"accion": "priorizar", "colectivoId": "COL-1"}, None)
    assert visto["e"] == {"colectivoId": "COL-1"}


def test_accion_con_datos_completos(monkeypatch):
    visto = {}
    monkeypatch.setitem(motor.PASOS, "escenarioOleada", lambda e, c: visto.setdefault("e", e))
    motor.handler({"accion": "escenarioOleada", "datos": {"n": 3, "fallas": {}}}, None)
    assert visto["e"] == {"n": 3, "fallas": {}}


def test_records_van_al_detector_y_lo_demas_al_barrido(monkeypatch):
    llamadas = []
    monkeypatch.setattr(motor.detector, "handler", lambda e, c: llamadas.append("stream"))
    monkeypatch.setattr(motor.detector, "reconciliar", lambda e, c: llamadas.append("barrido"))
    motor.handler({"Records": [{"eventSource": "aws:dynamodb"}]}, None)
    motor.handler({"source": "aws.events", "detail-type": "Scheduled Event"}, None)
    assert llamadas == ["stream", "barrido"]


def test_accion_desconocida_falla():
    import pytest
    with pytest.raises(ValueError):
        motor.handler({"accion": "noExiste"}, None)
