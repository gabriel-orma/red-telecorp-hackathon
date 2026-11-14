"""GET /api/nubes: el estado de cada nube sale de mediciones reales, no se filtran secretos y nada rompe la respuesta."""
import json
import os
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("STAGE", "test")

import nubes  # noqa: E402
from telecorp import util  # noqa: E402

OPERADOR = {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": "operador-1234", "cognito:groups": "[operadores]"}}}}}


def fila(estado="OK", hace_s=10, **extra):
    from datetime import timedelta
    ts = (util.ahora() - timedelta(seconds=hace_s)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {"estado": estado, "ultimaLlamada": ts, "contador": 3, "latenciaMs": 120, **extra}


def test_una_llamada_real_reciente_basta_para_decir_operativo():
    r = nubes._desde_tablero(fila())
    assert r["estado"] == "OK" and r["latenciaMs"] == 120 and r["contador"] == 3


def test_una_llamada_ok_vieja_pide_una_sonda_fresca():
    assert nubes._desde_tablero(fila(hace_s=nubes.VIGENCIA_TABLERO_S + 60)) is None


def test_un_error_reciente_se_muestra_con_su_causa():
    r = nubes._desde_tablero(fila("ERROR", hace_s=5, ultimoError="HTTP_401"))
    assert r["estado"] == "ERROR" and r["detalle"] == "HTTP_401"


def test_un_error_viejo_se_vuelve_a_comprobar_pero_sin_cupo_se_muestra_el_ultimo_dato(monkeypatch):
    vieja = fila("ERROR", hace_s=nubes.VIGENCIA_ERROR_S + 30, ultimoError="HTTP_500")
    assert nubes._desde_tablero(vieja) is None                              # caducó: toca sonda
    monkeypatch.setattr(nubes.estado, "leer_tablero", lambda: {"azure-acs": vieja})
    monkeypatch.setattr(nubes.estado, "reservar_cupo", lambda *a, **k: False)   # sin cupo de sonda
    r = nubes._servicio("azure-acs", True, lambda: pytest.fail("no debe sondear sin cupo"))
    assert r["estado"] == "ERROR" and r["detalle"] == "HTTP_500"


def test_un_error_viejo_que_ya_se_resolvio_pasa_a_ok_tras_la_sonda(monkeypatch):
    tablero = {"azure-acs": fila("ERROR", hace_s=500, ultimoError="RED")}
    monkeypatch.setattr(nubes.estado, "leer_tablero", lambda: tablero)
    monkeypatch.setattr(nubes.estado, "reservar_cupo", lambda *a, **k: True)
    nubes_sonda = lambda: tablero.update({"azure-acs": fila()})  # noqa: E731
    assert nubes._servicio("azure-acs", True, nubes_sonda)["estado"] == "OK"


@pytest.mark.parametrize("f, esperado", [(None, None), ({"estado": "SIN_USO"}, None), ({"estado": "NO_CONFIGURADA"}, {"estado": "SIN_CONFIGURAR"})])
def test_sin_datos_o_sin_configurar(f, esperado):
    assert nubes._desde_tablero(f) == esperado


def test_servicio_sin_secreto_es_sin_configurar_y_no_sondea():
    llamadas = []
    assert nubes._servicio("azure-acs", False, lambda: llamadas.append(1)) == {"estado": "SIN_CONFIGURAR"}
    assert llamadas == []


def test_la_sonda_respeta_el_cupo_y_no_se_repite(monkeypatch):
    tablero, cupos, sondas = {}, [True, False], []
    monkeypatch.setattr(nubes.estado, "leer_tablero", lambda: tablero)
    monkeypatch.setattr(nubes.estado, "reservar_cupo", lambda *a, **k: cupos.pop(0))

    def sonda():
        sondas.append(1)
        tablero["azure-acs"] = fila()
    assert nubes._servicio("azure-acs", True, sonda)["estado"] == "OK"
    tablero.clear()   # sin datos y sin cupo: no se vuelve a llamar a Azure
    assert nubes._servicio("azure-acs", True, sonda)["estado"] == "ERROR" and len(sondas) == 1


def test_obtener_no_filtra_secretos_y_sobrevive_a_una_nube_caida(monkeypatch):
    secreto = {"acsEndpoint": "tcomm.communication.azure.com", "acsKey": "CLAVE-SECRETA-ACS", "acsSender": "x@y.azurecomm.net",
               "mapsKey": "CLAVE-SECRETA-MAPS"}
    monkeypatch.setattr(nubes.secretos, "leer", lambda n, usar_cache=True: secreto)
    monkeypatch.setattr(nubes.ia, "modelo_configurado", lambda: None)
    monkeypatch.setattr(nubes, "_aws", lambda: {"dynamodb": {"estado": "OK", "latenciaMs": 5}})
    monkeypatch.setattr(nubes.estado, "leer_tablero", lambda: {"azure-acs": fila(), "azure-maps": fila("ERROR", ultimoError="HTTP_500")})
    r = nubes.obtener(dict(OPERADOR), None)
    assert r["statusCode"] == 200
    cuerpo = json.loads(r["body"])
    assert cuerpo["azure"]["acsEmail"]["estado"] == "OK" and cuerpo["azure"]["maps"]["estado"] == "ERROR"
    assert cuerpo["ia"]["gemini"] == {"estado": "SIN_CONFIGURAR"}
    assert "CLAVE-SECRETA" not in r["body"] and "azurecomm" not in r["body"]
