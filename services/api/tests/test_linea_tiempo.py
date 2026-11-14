"""Pruebas de la lógica pura de la línea de tiempo (sin AWS)."""
import os

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

import linea_tiempo as lt  # noqa: E402


def test_nivel_toma_el_ultimo():
    assert lt.nivel_de("ALTA (puntaje 54)") == "ALTA"
    assert lt.nivel_de("Re-priorizado: MEDIA → CRITICA (puntaje 120)") == "CRITICA"
    assert lt.nivel_de("sin nivel") is None


def test_pista_antena_estado_inicial():
    antena = {"antenaId": "ANT-001", "zonaId": "ZONA-01"}
    eventos = [
        {"tipoEvento": "CAMBIO_ESTADO", "ocurridoEn": "2026-11-14T10:05:00Z", "estadoAnterior": "CAIDA", "estadoNuevo": "NORMAL"},
        {"tipoEvento": "CAMBIO_ESTADO", "ocurridoEn": "2026-11-14T10:01:00Z", "estadoAnterior": "NORMAL", "estadoNuevo": "CAIDA"},
    ]
    p = lt.pista_antena(antena, eventos, "NORMAL")
    assert p["inicial"] == "NORMAL" and [c["estado"] for c in p["cambios"]] == ["CAIDA", "NORMAL"]
    # Sin cambios en la ventana: vale el estado actual.
    assert lt.pista_antena(antena, [], "SATURADA")["inicial"] == "SATURADA"
    assert lt.pista_antena(antena, [], None)["inicial"] == "SIN_DATOS"


def test_pista_colectivo_y_cruce():
    col = {"incidenteColectivoId": "COL-1", "zonaId": "ZONA-05", "detectadoEn": "2026-11-14T10:00:00Z",
           "resueltoEn": "2026-11-14T10:03:00Z", "usuariosAfectados": ["a", "b"]}
    eventos = [
        {"tipoEvento": "CREADO", "ocurridoEn": "2026-11-14T10:00:00Z", "estadoNuevo": "EN_EVALUACION"},
        {"tipoEvento": "PRIORIDAD_ASIGNADA", "ocurridoEn": "2026-11-14T10:00:05Z", "detalle": "MEDIA (puntaje 30)"},
        {"tipoEvento": "CAMBIO_ESTADO", "ocurridoEn": "2026-11-14T10:03:00Z", "estadoNuevo": "CERRADO"},
    ]
    p = lt.pista_colectivo(col, eventos)
    assert [e["estado"] for e in p["estados"]] == ["EN_EVALUACION", "CERRADO"]
    assert p["prioridades"] == [{"t": "2026-11-14T10:00:05Z", "prioridad": "MEDIA"}] and p["afectados"] == 2
    assert lt.se_cruza(col, "2026-11-14T10:02:00Z", "2026-11-14T11:00:00Z")
    assert not lt.se_cruza(col, "2026-11-14T10:04:00Z", "2026-11-14T11:00:00Z")
    assert lt.se_cruza({**col, "resueltoEn": None}, "2026-11-14T12:00:00Z", "2026-11-14T13:00:00Z")


def test_punto_reporte():
    inc = {"incidenciaId": "INC-1", "creadaEn": "t", "zonaId": "ZONA-01", "tipo": "SIN_SENAL",
           "reporte": {"ubicacion": {"lat": -12.1, "lng": -77.0}}}
    assert lt.punto_reporte(inc)["lat"] == -12.1
    assert "lat" not in lt.punto_reporte({**inc, "reporte": {}})
