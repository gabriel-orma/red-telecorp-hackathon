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
