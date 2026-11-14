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


# ---------------- E2 ----------------
def test_transiciones_de_incidencia():
    assert reglas.transicion_valida("REGISTRADA", "EN_REVISION")
    assert reglas.transicion_valida("REGISTRADA", "SOLUCIONADA")  # se pueden saltar pasos
    assert not reglas.transicion_valida("EN_ATENCION", "REGISTRADA")
    assert reglas.transicion_valida("SOLUCIONADA", "EN_ATENCION")  # reapertura
    assert not reglas.transicion_valida("CERRADA", "EN_ATENCION")
    assert reglas.transiciones_permitidas("CERRADA") == []
    assert reglas.transiciones_permitidas("SOLUCIONADA") == ["EN_ATENCION", "CERRADA"]


def _reporte(**cambios):
    base = {"usuarioId": "70123456", "numeroServicio": "999000111", "zonaId": "ZONA-05",
            "fechaHoraIncidente": "2026-11-14T10:00:00Z", "tipo": "SIN_INTERNET",
            "descripcion": "Sin datos", "email": "a@b.com"}
    return {**base, **cambios}


def test_validar_reporte():
    zonas_validas = {"ZONA-05"}
    assert reglas.validar_reporte(_reporte(), zonas_validas) == []
    assert any("zonaId" in e for e in reglas.validar_reporte(_reporte(zonaId="ZONA-99"), zonas_validas))
    assert any("tipo" in e for e in reglas.validar_reporte(_reporte(tipo="X"), zonas_validas))
    assert any("email" in e for e in reglas.validar_reporte(_reporte(email=None), zonas_validas))
    assert any("ubicacion" in e for e in reglas.validar_reporte(_reporte(ubicacion={"lat": "x"}), zonas_validas))


def test_enmascarar():
    assert reglas.enmascarar("70123456") == "70***456"
    assert reglas.enmascarar_email("gabriel@example.com") == "g***@example.com"


def test_ubicar_por_coordenadas():
    z = zonas.zona("ZONA-02")  # Miraflores
    assert zonas.ubicar(z["centro"]["lat"], z["centro"]["lng"])["zonaId"] == "ZONA-02"
    assert zonas.ubicar(-13.5, -71.9) is None  # Cusco: fuera de cobertura


# ---------------- E3 ----------------
def test_umbral_colectivo():
    assert not reglas.es_colectivo(9) and reglas.es_colectivo(10)


def test_entra_en_falla_solo_al_cambiar():
    assert reglas.entra_en_falla("NORMAL", "CAIDA")
    assert reglas.entra_en_falla(None, "INHABILITADA")
    assert not reglas.entra_en_falla("CAIDA", "INHABILITADA")  # ya estaba en falla
    assert not reglas.entra_en_falla("NORMAL", "SATURADA")


def test_prioridad_sube_con_criticidad_y_antenas():
    cfg = {"pesoAfectado": 1, "pesoAntenaEnFalla": 10, "umbrales": {"MEDIA": 20, "ALTA": 50, "CRITICA": 100}}
    assert reglas.calcular_prioridad(10, 1, 0, cfg) == (10, "BAJA")        # 10 vecinos en zona residencial
    assert reglas.calcular_prioridad(10, 5, 0, cfg)[1] == "ALTA"            # mismos 10 en un hospital
    assert reglas.calcular_prioridad(10, 5, 1, cfg)[1] == "CRITICA"         # hospital + antena caída
