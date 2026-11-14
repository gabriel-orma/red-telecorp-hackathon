"""Regla de recurrencia: ≥3 episodios en 30 días repartidos en ≥2 días distintos (hora de Lima)."""
from datetime import datetime, timedelta, timezone

import recurrencia

AHORA = datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc)   # 10:00 en Lima


def ep(antena, **hace):
    return {"antenaId": antena, "ts": (AHORA - timedelta(**hace)).isoformat()}


def evaluar(episodios, **kw):
    return recurrencia.evaluar_recurrencia(episodios, AHORA, **kw)


def test_tres_episodios_en_tres_dias_distintos_es_estructural():
    r = evaluar([ep("A", days=1), ep("A", days=5), ep("A", days=9)])
    assert r["A"] == {"episodios": 3, "dias": 3, "estructural": True}


def test_tres_episodios_el_mismo_dia_NO_es_estructural():
    r = evaluar([ep("A", hours=1), ep("A", hours=2), ep("A", hours=3)])
    assert r["A"]["dias"] == 1 and r["A"]["estructural"] is False


def test_dos_episodios_en_dias_distintos_no_alcanzan():
    assert evaluar([ep("A", days=1), ep("A", days=2)])["A"]["estructural"] is False


def test_tres_episodios_en_dos_dias_cuentan():
    r = evaluar([ep("A", hours=2), ep("A", hours=3), ep("A", days=2)])
    assert r["A"] == {"episodios": 3, "dias": 2, "estructural": True}


def test_un_episodio_de_hace_exactamente_30_dias_no_cuenta_y_29_dias_si():
    assert evaluar([ep("A", days=1), ep("A", days=2), ep("A", days=30)])["A"]["estructural"] is False
    assert evaluar([ep("A", days=1), ep("A", days=2), ep("A", days=29, hours=23)])["A"]["estructural"] is True


def test_los_episodios_futuros_no_cuentan():
    assert "A" not in evaluar([{"antenaId": "A", "ts": (AHORA + timedelta(hours=1)).isoformat()}])


def test_cada_antena_se_evalua_por_separado():
    r = evaluar([ep("A", days=1), ep("A", days=3), ep("A", days=5), ep("B", days=1), ep("B", days=2)])
    assert r["A"]["estructural"] is True and r["B"]["estructural"] is False


def test_el_dia_es_el_calendario_de_Lima_no_el_de_UTC():
    # 23:30 y 00:30 de Lima del día siguiente son 04:30 y 05:30 UTC del mismo día UTC... y días distintos en Lima
    a = datetime(2026, 11, 10, 4, 30, tzinfo=timezone.utc).isoformat()   # 23:30 del 9 en Lima
    b = datetime(2026, 11, 10, 5, 30, tzinfo=timezone.utc).isoformat()   # 00:30 del 10 en Lima
    r = evaluar([{"antenaId": "A", "ts": a}, {"antenaId": "A", "ts": b}, ep("A", days=1)])
    assert r["A"]["dias"] == 3


def test_acepta_fechas_con_Z():
    r = evaluar([{"antenaId": "A", "ts": "2026-11-13T10:00:00Z"}, {"antenaId": "A", "ts": "2026-11-10T10:00:00Z"},
                 {"antenaId": "A", "ts": "2026-11-05T10:00:00Z"}])
    assert r["A"]["estructural"] is True


def test_sin_episodios_no_hay_resultados():
    assert evaluar([]) == {}
