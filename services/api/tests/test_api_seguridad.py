"""Regresión de seguridad del API (H01, H02, H12, H13, H16, H26, H31). Sin AWS ni moto: handlers con fakes mínimos.

Cada prueba fija UN arreglo: si alguien reabre una ruta de administración, vuelve a exponer datos personales o
vuelve a usar `custom:dni` como identidad, falla aquí.
"""
import importlib.util
import json
import os
import pathlib

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("COLA_REPORTES_URL", "http://cola.local/reportes")

import acceso  # noqa: E402
import antenas  # noqa: E402
import colectivos  # noqa: E402
import incidencias  # noqa: E402

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
# Hay otro `simulador.py` en services/antenas/src (mismo nombre de módulo, hallazgo H30): se carga por ruta.
_spec = importlib.util.spec_from_file_location("simulador_api", SRC / "simulador.py")
simulador = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(simulador)


def evento(claims=None, **extra):
    ev = dict(extra)
    if claims is not None:
        ev["requestContext"] = {"authorizer": {"jwt": {"claims": claims}}}
    return ev


OPERADOR = {"sub": "op-0001-abcd", "cognito:groups": "[operadores]"}
CIUDADANO = {"sub": "usr-0002-efgh", "cognito:groups": "[otros]"}


# ---------------- H01 · rol de operador ----------------
@pytest.mark.parametrize("bruto, esperado", [
    ("[operadores]", {"operadores"}), ("[operadores admin]", {"operadores", "admin"}),
    ("operadores,admin", {"operadores", "admin"}), ('["operadores","admin"]', {"operadores", "admin"}),
    (["operadores"], {"operadores"}), ("", set()), (None, set()),
])
def test_grupos_de_acepta_los_formatos_de_api_gateway(bruto, esperado):
    claims = {} if bruto is None else {"cognito:groups": bruto}
    assert acceso.grupos_de(claims) == esperado


def test_solo_operadores_401_sin_sesion_403_sin_rol_y_pasa_con_rol():
    manejador = acceso.solo_operadores(lambda e, c: {"statusCode": 200})
    assert manejador({}, None)["statusCode"] == 401
    assert manejador(evento({"cognito:groups": "[operadores]"}), None)["statusCode"] == 401   # sin sub
    assert manejador(evento(CIUDADANO), None)["statusCode"] == 403
    assert manejador(evento(OPERADOR), None)["statusCode"] == 200


def test_el_grupo_no_basta_sin_un_sub_valido():
    assert not acceso.es_operador(evento({"sub": "../x;DROP", "cognito:groups": "[operadores]"}))


@pytest.mark.parametrize("handler, ev", [
    (incidencias.cambiar_estado, {"pathParameters": {"incidenciaId": "INC-1"}, "body": '{"estado":"EN_REVISION"}'}),
    (incidencias.listar_operador, {}), (incidencias.obtener_operador, {"pathParameters": {"incidenciaId": "INC-1"}}),
    (colectivos.restablecer, {"pathParameters": {"colectivoId": "COL-1"}}),
    (colectivos.obtener, {"pathParameters": {"colectivoId": "COL-1"}}),
    (simulador.obtener, {}), (simulador.actualizar, {"body": '{"activo": true}'}),
])
def test_rutas_de_administracion_rechazan_sin_sesion_y_sin_rol_antes_de_tocar_datos(handler, ev):
    assert handler(dict(ev), None)["statusCode"] == 401
    assert handler({**ev, **evento(CIUDADANO)}, None)["statusCode"] == 403


def test_serverless_yml_las_rutas_de_administracion_llevan_autorizador():
    yaml = pytest.importorskip("yaml")

    class Cargador(yaml.SafeLoader):
        pass

    Cargador.add_multi_constructor("!", lambda l, s, n: l.construct_scalar(n) if isinstance(n, yaml.ScalarNode)
                                   else l.construct_sequence(n) if isinstance(n, yaml.SequenceNode) else l.construct_mapping(n))
    cfg = yaml.load((SRC.parent / "serverless.yml").read_text(encoding="utf-8"), Loader=Cargador)
    rutas = {}
    for f in cfg["functions"].values():
        for ev in f.get("events", []):
            h = ev.get("httpApi")
            if h:
                m, p = h.split(" ", 1) if isinstance(h, str) else (h["method"], h["path"])
                rutas[(m, p)] = bool(isinstance(h, dict) and h.get("authorizer"))
    assert {r for r, auth in rutas.items() if auth} == {
        ("POST", "/api/reportes"), ("GET", "/api/mis-reportes"), ("GET", "/api/simulador"), ("PUT", "/api/simulador"),
        ("GET", "/api/operador/incidencias"), ("GET", "/api/operador/incidencias/{incidenciaId}"),
        ("PATCH", "/api/incidencias/{incidenciaId}/estado"), ("GET", "/api/colectivos/{colectivoId}"),
        ("POST", "/api/colectivos/{colectivoId}/restablecer"),
    }
    # el resto (incl. las vistas públicas de incidencias) debe ser de solo lectura
    assert all(m == "GET" for (m, _), auth in rutas.items() if not auth)


# ---------------- H02 · PII pública ----------------
ITEM = {
    "incidenciaId": "INC-1", "estado": "REGISTRADA", "creadaEn": "2026-11-14T10:00:00.000Z",
    "actualizadaEn": "2026-11-14T10:00:00.000Z", "zonaId": "ZONA-05", "usuarioId": "70123456", "tipo": "SIN_INTERNET",
    "reporte": {"usuarioId": "70123456", "nombre": "Ana Quispe", "numeroServicio": "999111222", "email": "ana@correo.com",
                "telefonoContacto": "+51999111222", "zonaId": "ZONA-05", "ubicacion": {"lat": -12.0843, "lng": -77.0312},
                "ubicacionFuente": "GPS", "fechaHoraIncidente": "2026-11-14T09:58:00.000Z", "tipo": "SIN_INTERNET",
                "descripcion": "Llamé a mi vecina Rosa y tampoco tiene señal"},
}


def test_vista_publica_es_una_lista_blanca():
    v = incidencias._vista_publica(ITEM)
    assert set(v) == {"incidenciaId", "estado", "creadaEn", "actualizadaEn", "zonaId", "tipo", "transicionesPermitidas", "reporte"}
    assert set(v["reporte"]) == {"tipo", "zonaId", "fechaHoraIncidente", "ubicacionFuente"}
    texto = json.dumps(v)
    for secreto in ("Ana", "Quispe", "70123456", "999111222", "ana@", "-12.0843", "Rosa", "usuarioId", "descripcion"):
        assert secreto not in texto


def test_vista_operador_ve_el_detalle_pero_con_identificadores_enmascarados():
    v = incidencias._vista_operador(ITEM, completa=True)
    assert v["reporte"]["nombre"] == "Ana Quispe" and v["reporte"]["ubicacion"]["lat"] == -12.0843
    assert v["reporte"]["descripcion"].startswith("Llamé a mi vecina")
    assert v["reporte"]["usuarioId"] == "70***56" and "70123456" not in json.dumps(v)
    assert v["reporte"]["email"] == "a***@correo.com" and "999111222" not in v["reporte"]["numeroServicio"]


def test_historial_publico_no_expone_el_sub_del_operador(monkeypatch):
    class Tabla:
        def query(self, **kw):
            return {"Items": [{"entidadId": "INC-1", "sk": "x", "actor": "operador:op-0001-abcd", "tipoEvento": "CAMBIO_ESTADO"},
                              {"entidadId": "INC-1", "sk": "y", "actor": "USUARIO", "tipoEvento": "CREADO"}]}
    monkeypatch.setattr(incidencias.db, "tabla", lambda n: Tabla())
    assert [e["actor"] for e in incidencias._historial("INC-1")] == ["OPERADOR", "USUARIO"]
    assert [e["actor"] for e in incidencias._historial("INC-1", operador=True)] == ["operador:op-0001-abcd", "USUARIO"]


# ---------------- H13 / H12 · identidad = sub ----------------
class _Tabla:
    def __init__(self):
        self.puestos = []

    def put_item(self, **kw):
        self.puestos.append(kw)


class _Cola:
    def __init__(self):
        self.mensajes = []

    def send_message(self, **kw):
        self.mensajes.append(json.loads(kw["MessageBody"]))


@pytest.fixture()
def entorno(monkeypatch):
    tabla, cola = _Tabla(), _Cola()
    monkeypatch.setattr(incidencias.db, "tabla", lambda n: tabla)
    monkeypatch.setattr(incidencias, "_sqs", cola)
    return tabla, cola


def _claims(**extra):
    return {"sub": "11111111-2222-3333-4444-555555555555", "email": "ana@correo.com", "name": "Ana",
            "custom:dni": "70123456", "custom:numeroServicio": "999111222", "custom:zonaId": "ZONA-05", **extra}


def _reportar(claims, cuerpo=None):
    cuerpo = cuerpo or {"tipo": "SIN_INTERNET", "descripcion": "sin servicio"}
    return incidencias.crear_reporte(evento(claims, body=json.dumps(cuerpo)), None)


def test_usuarioId_es_el_sub_y_cambiar_custom_dni_no_cambia_la_identidad(entorno):
    tabla, cola = entorno
    assert _reportar(_claims())["statusCode"] == 202
    assert _reportar(_claims(**{"custom:dni": "99999999"}))["statusCode"] == 202   # el usuario "editó" su DNI
    ids = {m["reporte"]["usuarioId"] for m in cola.mensajes}
    assert ids == {"11111111-2222-3333-4444-555555555555"}                           # sigue siendo UNA identidad
    # Una sola reserva de dedup, con el `sub` como identidad (prefijo USR# del diseño de detección).
    assert {p["Item"]["clave"] for p in tabla.puestos} == {"USR#11111111-2222-3333-4444-555555555555#ZONA-05"}


def test_crear_reporte_exige_sub_y_valida_su_formato(entorno):
    assert incidencias.crear_reporte(evento(None, body="{}"), None)["statusCode"] == 401
    sin_sub = {k: v for k, v in _claims().items() if k != "sub"}
    assert _reportar(sin_sub)["statusCode"] == 401          # custom:dni solo NO basta para identificarse
    assert _reportar(_claims(sub="../x;DROP"))["statusCode"] == 400
    assert _reportar(_claims(sub="COLECTIVO#ZONA-05"))["statusCode"] == 400  # sin '#': no choca con claves internas


# ---------------- H26 · fechaHoraIncidente ----------------
def test_fecha_incidente_acepta_iso_con_zona_y_la_normaliza_a_utc():
    iso, error = incidencias._fecha_incidente(
        (incidencias.datetime.now(incidencias.timezone.utc) - incidencias.timedelta(hours=1)).astimezone(
            incidencias.timezone(incidencias.timedelta(hours=-5))).isoformat())
    assert error is None and iso.endswith("Z") and len(iso) == 24


@pytest.mark.parametrize("valor", ["ayer por la tarde", "2026-11-14T10:00:00", "a" * 300_000, 1e999, 12345, ["x"], {"a": 1},
                                   "2020-01-01T00:00:00Z", "2999-01-01T00:00:00Z"])
def test_fecha_incidente_rechaza_basura_sin_zona_gigantes_y_fuera_de_rango(valor):
    iso, error = incidencias._fecha_incidente(valor)
    assert iso is None and error


def test_crear_reporte_con_fecha_invalida_da_400_y_no_toma_dedup_ni_encola(entorno):
    tabla, cola = entorno
    assert _reportar(_claims(), {"tipo": "SIN_INTERNET", "descripcion": "x", "fechaHoraIncidente": "a" * 300_000})["statusCode"] == 400
    assert _reportar(_claims(), {"tipo": "SIN_INTERNET", "descripcion": "x", "fechaHoraIncidente": 1e999})["statusCode"] == 400
    assert tabla.puestos == [] and cola.mensajes == []


@pytest.mark.parametrize("ubic", [{"lat": "nan", "lng": 0}, {"lat": "inf", "lng": 0}, {"lat": 91, "lng": 0}, {"lat": 0, "lng": 181}])
def test_crear_reporte_con_ubicacion_no_finita_o_fuera_de_rango_da_400(entorno, ubic):
    assert _reportar(_claims(), {"tipo": "SIN_INTERNET", "descripcion": "x", "ubicacion": ubic})["statusCode"] == 400


# ---------------- H16 · simulador ----------------
@pytest.mark.parametrize("cuerpo", [
    {"fallas": {"ANT-001": "nan"}}, {"fallas": {"ANT-001": "1e999"}}, {"fallas": {"ANT-001": "-inf"}},
    {"fallas": {"ANT-001": -1}}, {"fallas": {"ANT-001": 5000}}, {"fallas": {"ANT-001": True}}, {"fallas": {"ANT-001": [1]}},
    {"fallas": ["ANT-001"]}, {"fallas": "ANT-001"}, {"fallas": 5}, {"fallas": {"ANT-999": 0}}, {"activo": "false"}, {"activo": 1},
])
def test_simulador_valida_todo_antes_de_tocar_nada(cuerpo):
    fallas, error = simulador._validar(cuerpo)
    assert fallas is None and error


def test_simulador_acepta_valores_validos():
    assert simulador._validar({"fallas": {"ANT-001": 0, "ANT-002": "35.5", "ANT-003": None}, "activo": True}) == (
        {"ANT-001": 0.0, "ANT-002": 35.5, "ANT-003": None}, None)
    assert simulador._validar({}) == ({}, None)


def test_simulador_actualizar_responde_400_sin_tocar_ssm(monkeypatch):
    monkeypatch.setattr(simulador.config, "leer", lambda *a, **k: pytest.fail("leyó la configuración antes de validar"))
    r = simulador.actualizar(evento(OPERADOR, body='{"fallas": {"ANT-001": "nan"}}'), None)
    assert r["statusCode"] == 400


# ---------------- H31 · ubicar zona ----------------
@pytest.mark.parametrize("q", [{"lat": "inf", "lng": "0"}, {"lat": "nan", "lng": "0"}, {"lat": "1e999", "lng": "0"},
                               {"lat": "91", "lng": "0"}, {"lat": "0", "lng": "-181"}, {"lat": "x", "lng": "0"}, {}])
def test_ubicar_zona_valida_lat_lng_finitas_y_en_rango(q):
    assert antenas.ubicar_zona({"queryStringParameters": q}, None)["statusCode"] == 400
