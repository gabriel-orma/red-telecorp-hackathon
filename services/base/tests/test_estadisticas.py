"""Pruebas de las funciones puras de estadísticas (E3.5)."""
from datetime import datetime, timezone

from telecorp import estadisticas as est


def test_bucket_redondea_a_15_minutos():
    dt = datetime(2026, 11, 14, 10, 29, 59, tzinfo=timezone.utc)
    assert est.bucket(dt) == "2026-11-14T10:15:00Z"
    assert est.bucket_de_iso("2026-11-14T10:30:00.123Z") == "2026-11-14T10:30:00Z"


def test_96_buckets_terminan_en_el_actual():
    ahora = datetime(2026, 11, 14, 10, 7, tzinfo=timezone.utc)
    bs = est.buckets_ultimas_24h(ahora)
    assert len(bs) == 96 and bs[-1] == "2026-11-14T10:00:00Z" and bs[0] == "2026-11-13T10:15:00Z"
    assert bs == sorted(bs)


def test_linea_base_promedia_el_mismo_bloque_de_7_dias():
    conteos = {f"2026-11-{d:02d}T10:00:00Z": 7 for d in range(7, 14)}  # 7 días previos con 7 reportes
    conteos["2026-11-14T10:00:00Z"] = 50  # el día actual no cuenta para su propia base
    assert est.linea_base(conteos, "2026-11-14T10:00:00Z") == 7.0
    assert est.linea_base({}, "2026-11-14T10:00:00Z") == 0.0


def test_nivel():
    assert est.nivel(0, 0, hay_colectivo=True) == "PROBLEMAS"
    assert est.nivel(12, 2, hay_colectivo=False) == "POSIBLES_PROBLEMAS"
    assert est.nivel(4, 0, hay_colectivo=False) == "SIN_PROBLEMAS"   # pocos reportes: ruido
    assert est.nivel(8, 4, hay_colectivo=False) == "SIN_PROBLEMAS"   # dentro de lo normal
