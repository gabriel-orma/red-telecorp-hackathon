"""El router único debe atender exactamente las rutas declaradas en serverless.yml, con el mismo autorizador."""
import os
from pathlib import Path

import pytest

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
yaml = pytest.importorskip("yaml")

import router  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]


class _Cargador(yaml.SafeLoader):
    pass


_Cargador.add_multi_constructor("!", lambda l, s, n: l.construct_scalar(n) if isinstance(n, yaml.ScalarNode)
                                else l.construct_sequence(n) if isinstance(n, yaml.SequenceNode) else l.construct_mapping(n))


def _eventos_api():
    cfg = yaml.load((RAIZ / "services/api/serverless.yml").read_text(encoding="utf-8"), Loader=_Cargador)
    return cfg["functions"]["api"]["events"]


def test_rutas_del_router_igual_a_serverless():
    declaradas, con_auth = set(), set()
    for e in _eventos_api():
        if "websocket" in e:
            declaradas.add(e["websocket"])
            continue
        h = e["httpApi"]
        clave = f'{h["method"]} {h["path"]}'
        declaradas.add(clave)
        if h.get("authorizer"):
            con_auth.add(clave)
    assert declaradas == set(router.RUTAS)
    assert con_auth == router.CON_AUTORIZADOR


def test_cada_ruta_tiene_handler():
    # Se revisa el archivo del API (en pytest hay dos `simulador.py` en el path: el del API y el de antenas).
    for clave, (modulo, funcion) in router.RUTAS.items():
        fuente = (RAIZ / "services/api/src" / f"{modulo}.py").read_text(encoding="utf-8")
        assert f"def {funcion}(" in fuente, clave


def test_ruta_desconocida_404():
    assert router.handler({"routeKey": "GET /api/no-existe"}, None)["statusCode"] == 404


def test_websocket_usa_routekey_del_contexto():
    assert router.clave_ruta({"requestContext": {"routeKey": "$connect"}}) == "$connect"
