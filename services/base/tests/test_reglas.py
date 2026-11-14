"""Pruebas de las reglas de negocio puras y del catálogo."""
import pytest

from telecorp import reglas, util, zonas


@pytest.mark.parametrize("gb, esperado", [
    (0, "INHABILITADA"),
    (0.1, "CAIDA"),
    (59.9, "CAIDA"),
    (60, "NORMAL"),
    (129, "NORMAL"),
    (129.1, "SATURADA"),
    (200, "SATURADA"),
])
def test_clasificar_antena_respeta_umbrales_del_enunciado(gb, esperado):
    assert reglas.clasificar_antena(gb) == esperado


def test_peor_estado_ordena_por_gravedad():
    assert reglas.peor_estado(["NORMAL", "SATURADA", "NORMAL"]) == "SATURADA"
    assert reglas.peor_estado(["CAIDA", "INHABILITADA"]) == "INHABILITADA"
    assert reglas.peor_estado([]) == "SIN_DATOS"


def test_catalogo_tiene_coordenadas_y_ids_unicos():
    ids = [a["antenaId"] for a in zonas.antenas()]
    assert len(ids) == len(set(ids)) >= 30
    for a in zonas.antenas():
        assert -12.3 < a["lat"] < -11.8 and -77.2 < a["lng"] < -76.8, a
    assert zonas.criticidad("ZONA-05") == 5  # médica
    assert zonas.zona_de_antena("ANT-013") == "ZONA-05"


def test_ids_e_iso_son_ordenables():
    a, b = util.nuevo_id("INC"), util.nuevo_id("INC")
    assert a.startswith("INC-") and a != b
    assert util.iso(util.ahora()).endswith("Z")
