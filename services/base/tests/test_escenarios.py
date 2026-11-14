"""Pruebas del planificador de escenarios de demo (E5)."""
import pytest

from telecorp import escenarios, zonas


def test_tormenta_afecta_la_zona_y_vecinas_y_supera_el_umbral():
    plan = escenarios.planificar("TORMENTA", "ZONA-05", zonas.zonas(), semilla=1)
    assert len(plan) == 5 and plan[0]["esperaSegundos"] == 0 and plan[1]["esperaSegundos"] > 0
    zonas_con_reportes = {r["zonaId"] for o in plan for r in o["reportes"]}
    assert "ZONA-05" in zonas_con_reportes and len(zonas_con_reportes) > 1  # se expande a vecinas
    en_zona = sum(1 for o in plan for r in o["reportes"] if r["zonaId"] == "ZONA-05")
    assert en_zona >= 10  # dispara el incidente colectivo
    centrales = {a["antenaId"] for a in zonas.zona("ZONA-05")["antenas"]}
    assert next(iter(plan[0]["fallas"])) in centrales  # la primera antena que cae es de la zona elegida


def test_corte_de_energia_solo_apaga_la_zona_elegida():
    plan = escenarios.planificar("CORTE_ENERGIA", "ZONA-02", zonas.zonas(), semilla=2)
    propias = {a["antenaId"] for a in zonas.zona("ZONA-02")["antenas"]}
    fallas = {k: v for o in plan for k, v in o["fallas"].items()}
    assert set(fallas) == propias and set(fallas.values()) == {0.0}
    assert {r["zonaId"] for o in plan for r in o["reportes"]} == {"ZONA-02"}


def test_tipo_desconocido():
    with pytest.raises(ValueError):
        escenarios.planificar("TERREMOTO", "ZONA-01", zonas.zonas())
