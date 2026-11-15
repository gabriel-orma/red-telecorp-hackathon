"""Pruebas del generador de métricas (sin AWS: boto3 se crea pero no se llama)."""
import os
import random

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import simulador  # noqa: E402
from telecorp import reglas  # noqa: E402


def test_sin_saturacion_los_valores_son_normales():
    rng = random.Random(1)
    for minuto in range(0, 1440, 37):
        v = simulador.generar_valor("ANT-001", minuto, prob_saturacion=0, rng=rng)
        assert reglas.clasificar_antena(v) == "NORMAL"


def test_saturacion_supera_129():
    v = simulador.generar_valor("ANT-001", 600, prob_saturacion=1, rng=random.Random(2))
    assert reglas.clasificar_antena(v) == "SATURADA"


def test_fallas_forzadas_reemplazan_el_valor():
    m = {x["antenaId"]: x for x in simulador.metricas_actuales({"ANT-013": 0, "ANT-014": 35}, 0)}
    assert m["ANT-013"]["gbPorMinuto"] == 0
    assert m["ANT-014"]["gbPorMinuto"] == 35
    assert m["ANT-013"]["zonaId"] == "ZONA-05"
    assert len(m) == 36


def test_solo_las_lecturas_forzadas_se_marcan_como_simuladas():
    """El detector, la analítica y la recurrencia separan lo simulado de lo operativo con esta marca."""
    m = {x["antenaId"]: x for x in simulador.metricas_actuales({"ANT-013": 0}, 0)}
    assert m["ANT-013"]["simulada"] is True
    assert all("simulada" not in x for antena, x in m.items() if antena != "ANT-013")


def test_muestras_del_minuto_sin_dormir():
    # D14: las 4 muestras se encolan de una vez con retraso de SQS; la Lambda no espera.
    assert simulador.plan_muestras(4) == [0, 15, 30, 45]
    assert simulador.plan_muestras(1) == [0]


def test_enviar_usa_delay_de_sqs(monkeypatch):
    enviados = []
    monkeypatch.setenv("COLA_METRICAS_URL", "https://sqs/cola")
    monkeypatch.setattr(simulador._sqs, "send_message_batch", lambda **kw: enviados.append(kw) or {})
    simulador.enviar(simulador.metricas_actuales({}, 0), retraso_s=30)
    assert len(enviados) == 4 and all(e["DelaySeconds"] == 30 for lote in enviados for e in lote["Entries"])


def test_motor_antenas_despacha_por_tipo_de_evento(monkeypatch):
    import motor_antenas
    llamadas = []
    monkeypatch.setattr(motor_antenas.clasificador, "handler", lambda e, c: llamadas.append("clasificar"))
    monkeypatch.setattr(motor_antenas.simulador, "handler", lambda e, c: llamadas.append("simular"))
    motor_antenas.handler({"Records": [{}]}, None)
    motor_antenas.handler({}, None)
    assert llamadas == ["clasificar", "simular"]
