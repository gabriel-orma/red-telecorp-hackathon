"""Clasificador de reportes por ML local (TF-IDF + regresión logística): inferencia en Python puro, coherencia con los datos y con
las reglas del negocio. Las MÉTRICAS no se prueban aquí (dependen de los datos): están en `ml/triage/resultados.json`."""
import hashlib
import json
import math
import pathlib
import time

import pytest

from telecorp import reglas
from telecorp.ml import triage
from telecorp.nube2 import ia

RAIZ = pathlib.Path(__file__).resolve().parents[3]
DATOS = RAIZ / "ml" / "triage" / "datos" / "entrenamiento.csv"
RESULTADOS = RAIZ / "ml" / "triage" / "resultados.json"


def _sha(ruta):
    return hashlib.sha256(pathlib.Path(ruta).read_bytes()).hexdigest()[:16]


@pytest.fixture(scope="module")
def modelo():
    m = triage.cargar_modelo()
    assert m is not None, "falta triage_modelo.json: ejecutar ml/triage/entrenar.py"
    return m


# ---------------------------------------------------------------- Vectorizador
def test_normalizar_quita_tildes_mayusculas_y_letras_repetidas():
    assert triage.normalizar("¡NOOOO hay Internet, MÁS lento!") == "noo hay internet mas lento"
    assert triage.normalizar(None) == "" and triage.normalizar("   ") == ""
    assert triage.normalizar("señal") == "senal"          # ñ → n, igual que en el entrenamiento


def test_las_caracteristicas_son_palabras_pares_y_letras_y_son_deterministas():
    c = triage.caracteristicas("sin internet")
    assert c["w:sin"] == 1 and c["b:sin_internet"] == 1 and c["c: si"] == 1 and c["c:net"] == 1
    assert c == triage.caracteristicas("SIN   Internet!!")        # misma normalización


def test_un_texto_gigante_se_recorta_y_no_tarda():
    inicio = time.time()
    triage.caracteristicas("no hay internet " * 200000)
    assert time.time() - inicio < 2.0                              # el recorte a 2000 caracteres acota el trabajo


# ---------------------------------------------------------------- Modelo exportado
def test_el_modelo_cubre_exactamente_los_tipos_del_catalogo(modelo):
    assert set(modelo["clases"]) == set(reglas.TIPOS_PROBLEMA) and len(modelo["clases"]) == len(modelo["sesgos"])
    assert all(len(v) == 1 + len(modelo["clases"]) for v in modelo["vocab"].values())      # [idf, un peso por clase]


def test_la_probabilidad_es_una_distribucion_y_el_resultado_es_estable(modelo):
    r = triage.clasificar("desde ayer no tengo internet en mi casa", modelo)
    assert r["clase"] in modelo["clases"] and 0.0 < r["confianza"] <= 1.0
    assert math.isclose(sum(r["probabilidades"].values()), 1.0, abs_tol=0.01)
    assert r == triage.clasificar("desde ayer no tengo internet en mi casa", modelo)
    assert r["modelo"] == modelo["version"]


def test_sin_evidencia_el_modelo_dice_otro_y_nunca_cuenta_como_falla(modelo):
    for texto in ("", "   ", None, "!!! ???"):                         # ninguna característica conocida
        r = triage.clasificar(texto, modelo)
        assert r["clase"] == "OTRO" and r["confianza"] == 0.0
    for texto in ("zzzxq qqwwk", "asdf jkl", "123 456 789"):          # ruido: puede haber alguna letra conocida, pero no alcanza el umbral
        r = triage.clasificar(texto, modelo)
        assert r["clase"] == "OTRO" or r["confianza"] < reglas.UMBRAL_CONFIANZA_TRIAGE_ML
        assert not reglas.triage_ia_confirma_servicio({"fuente": "ML", "relacionado": r["clase"] != "OTRO", "tipoSugerido": r["clase"],
                                                       "confianza": r["confianza"]})


def test_sin_archivo_de_modelo_no_finge(tmp_path):
    assert triage.cargar_modelo(str(tmp_path / "no_existe.json")) is None


# ---------------------------------------------------------------- Coherencia con los datos y las reglas
def test_el_modelo_se_entreno_con_los_datos_que_estan_en_el_repo(modelo):
    """Evita un modelo viejo con datos nuevos (o al revés): el hash de los datos queda dentro del modelo."""
    assert modelo["entrenado_con"]["sha256_datos"] == _sha(DATOS)
    r = json.loads(RESULTADOS.read_text(encoding="utf-8"))
    assert r["datos"]["entrenamiento"]["sha256"] == _sha(DATOS) and r["version_modelo"] == modelo["version"]


def test_el_umbral_de_las_reglas_es_el_que_eligio_el_entrenamiento(modelo):
    assert reglas.UMBRAL_CONFIANZA_TRIAGE_ML == modelo["umbral_servicio"]


def test_los_resultados_publicados_no_estan_inflados():
    """La validación cruzada del entrenamiento es optimista; lo que se afirma es lo medido en conjuntos de otros autores."""
    r = json.loads(RESULTADOS.read_text(encoding="utf-8"))
    assert r["validacion"]["regresion_logistica"]["exactitud"] <= r["configuracion"]["f1_macro_cv_por_C"][str(r["configuracion"]["C_elegido_por_cv"])] + 0.2
    if "prueba_final" in r:
        assert r["prueba_final"]["nota"] and r["prueba_final"]["n"] > 0


# ---------------------------------------------------------------- Integración con el triage del flujo
def test_por_defecto_el_triage_usa_el_modelo_local_y_no_sale_a_internet(monkeypatch):
    monkeypatch.setattr(ia, "consultar_modelo", lambda *a, **k: pytest.fail("no debe llamar a Gemini"))
    r = ia.triage_reporte("hace dos dias no puedo hacer ni recibir llamadas desde mi celular", "OTRO")
    assert r["fuente"] == "ML" and r["proveedor"] == "modelo-local" and r["modelo"] == triage.cargar_modelo()["version"]
    assert r["tipoSugerido"] == "SIN_LLAMADAS" and r["relacionado"] is True


def test_un_reporte_que_no_es_una_falla_no_cuenta_para_el_colectivo():
    r = ia.triage_reporte("quiero cambiar mi plan porque me cobraron de mas en el recibo", "OTRO")
    assert r["fuente"] == "ML" and reglas.triage_ia_confirma_servicio(r) is False


def test_las_reglas_nunca_cuentan_y_el_modelo_solo_con_confianza_suficiente():
    ml = {"fuente": "ML", "relacionado": True, "tipoSugerido": "SIN_INTERNET", "confianza": 0.99}
    assert reglas.triage_ia_confirma_servicio(ml) is True
    assert reglas.triage_ia_confirma_servicio({**ml, "confianza": reglas.UMBRAL_CONFIANZA_TRIAGE_ML - 0.01}) is False
    assert reglas.triage_ia_confirma_servicio({**ml, "relacionado": False}) is False
    assert reglas.triage_ia_confirma_servicio({**ml, "tipoSugerido": "OTRO"}) is False
    assert reglas.triage_ia_confirma_servicio({**ml, "fuente": "REGLAS"}) is False         # las reglas no son un modelo
    assert reglas.triage_ia_confirma_servicio({**ml, "fuente": "inventada"}) is False
    assert reglas.triage_ia_confirma_servicio(None) is False and reglas.triage_ia_confirma_servicio({"fuente": "ML"}) is False
