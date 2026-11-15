"""La «detección anticipada» se mide desde que la antena cayó (`estadoDesde`), no desde que la verificación la vio."""
from conftest import insertar, item_incidencia, tabla
from telecorp import zonas


def _colectivo(zona):
    import comun_colectivos as cc
    incs = [insertar(item_incidencia(f"7100{i:04d}", zona=zona)) for i in range(10)]
    return cc.crear(zona, "REPORTES_USUARIOS", "10 usuarios", incs, [])


def test_primera_falla_es_cuando_cayo_la_antena_y_no_cuando_la_vio_la_verificacion(aws):
    import comun_colectivos as cc
    import pasos
    zona = "ZONA-05"
    antena = zonas.zona(zona)["antenas"][0]["antenaId"]
    tabla("antenas").put_item(Item={"antenaId": antena, "zonaId": zona, "estado": "CAIDA", "gbPorMinuto": 10,
                                    "estadoDesde": "2026-11-14T10:00:00.000Z"})
    cid = _colectivo(zona)
    pasos.verificar_infraestructura({"colectivoId": cid}, None)
    col = cc.obtener(cid)
    assert col["primeraFallaEn"] == "2026-11-14T10:00:00.000Z"
    assert [a["desde"] for a in col["antenasEnFalla"]] == ["2026-11-14T10:00:00.000Z"]


def test_si_la_antena_no_tiene_estadoDesde_se_usa_el_instante_de_la_verificacion(aws):
    import comun_colectivos as cc
    import pasos
    zona = "ZONA-05"
    antena = zonas.zona(zona)["antenas"][0]["antenaId"]
    tabla("antenas").put_item(Item={"antenaId": antena, "zonaId": zona, "estado": "INHABILITADA", "gbPorMinuto": 0})
    cid = _colectivo(zona)
    pasos.verificar_infraestructura({"colectivoId": cid}, None)
    assert cc.obtener(cid)["primeraFallaEn"]          # nunca queda vacío: hay respaldo
    assert cc.antenas_zona(zona)[1] == {}
