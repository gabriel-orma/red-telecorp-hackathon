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


def test_acelerada_guion_completo():
    plan = escenarios.planificar("ACELERADA", "ZONA-05", zonas.zonas(), semilla=3)
    assert len(plan) == 60 and plan[0]["esperaSegundos"] == 0 and plan[1]["esperaSegundos"] == 3
    caidas = {a for p in plan for a in p["fallas"]}
    recuperadas = {a for p in plan for a in p["recuperar"]}
    assert caidas and caidas == recuperadas  # todo lo que cae se recupera: los colectivos se cierran solos
    por_zona = {}
    for p in plan:
        for r in p["reportes"]:
            por_zona[r["zonaId"]] = por_zona.get(r["zonaId"], 0) + 1
    eventos = [z for z, n in por_zona.items() if n >= 10]
    assert len(eventos) == 4 and "ZONA-05" in eventos  # 4 colectivos, el primero en la zona elegida
    # Ruido: ninguna otra zona llega al umbral de 10 usuarios.
    assert all(n < 10 for z, n in por_zona.items() if z not in eventos)


def test_acelerada_reportes_antes_de_recuperar():
    plan = escenarios.planificar("ACELERADA", "ZONA-01", zonas.zonas(), semilla=7)
    catalogo = {a["antenaId"]: z["zonaId"] for z in zonas.zonas() for a in z["antenas"]}
    for p in plan:
        for antena in p["recuperar"]:
            zona = catalogo[antena]
            assert not any(r["zonaId"] == zona for q in plan[p["n"]:] for r in q["reportes"])
