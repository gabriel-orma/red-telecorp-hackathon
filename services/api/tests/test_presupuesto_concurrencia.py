"""Presupuesto de concurrencia (decisión D14): la cuenta del AWS Academy Learner Lab se DESACTIVA si hay más de 10
Lambdas ejecutándose a la vez. Estas pruebas leen la infraestructura como código y fallan si:
- alguna función no tiene `reservedConcurrency` (sin tope, Lambda puede escalar sin límite), o
- la suma de los topes de TODOS los stacks supera 7 (las 5 Lambdas propias del lab necesitan margen), o
- una Step Function llama a algo que no sea el motor, o un reintento no espera cuando el motor está ocupado.
"""
import importlib
import os
import re
import sys
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
RAIZ = Path(__file__).resolve().parents[3]
STACKS = ["services/base", "services/antenas", "services/api", "workflows"]
PRESUPUESTO = 7   # 10 permitidas por AWS Academy − 3 de margen para las Lambdas del propio laboratorio
LIMITE_ACADEMY = 10


class _Cargador(yaml.SafeLoader):
    pass


_Cargador.add_multi_constructor("!", lambda l, s, n: l.construct_scalar(n) if isinstance(n, yaml.ScalarNode)
                                else l.construct_sequence(n) if isinstance(n, yaml.SequenceNode) else l.construct_mapping(n))


def _sls(stack: str) -> dict:
    return yaml.load((RAIZ / stack / "serverless.yml").read_text(encoding="utf-8"), Loader=_Cargador)


def _funciones() -> dict:
    return {f"{st}:{n}": f for st in STACKS for n, f in (_sls(st).get("functions") or {}).items()}


def test_toda_funcion_tiene_tope_de_concurrencia():
    sin_tope = [n for n, f in _funciones().items() if not isinstance(f.get("reservedConcurrency"), int)
                or f["reservedConcurrency"] < 1]
    assert not sin_tope, f"Funciones sin reservedConcurrency (podrían escalar sin límite): {sin_tope}"


def test_colas_no_piden_mas_lectores_que_el_tope():
    # AWS rechaza (CREATE_FAILED) un maximumConcurrency mayor que reservedConcurrency.
    for n, f in _funciones().items():
        for e in f.get("events", []):
            if "sqs" in e and isinstance(e["sqs"], dict) and "maximumConcurrency" in e["sqs"]:
                assert e["sqs"]["maximumConcurrency"] <= f["reservedConcurrency"], n


def test_suma_de_topes_dentro_del_presupuesto():
    topes = {n: f["reservedConcurrency"] for n, f in _funciones().items()}
    total = sum(topes.values())
    assert total <= PRESUPUESTO < LIMITE_ACADEMY, f"Suma de topes {total} > {PRESUPUESTO}: {topes}"


def test_colas_toleran_rechazos_por_ocupado():
    recursos = _sls("services/base")["resources"]["Resources"]
    for cola in ("ColaReportes", "ColaMetricas"):
        p = recursos[cola]["Properties"]
        assert p["RedrivePolicy"]["maxReceiveCount"] >= 10, cola   # un "ocupado" también cuenta como recepción
        assert p["VisibilityTimeout"] <= 90, cola                  # reintentar pronto


def test_frontend_sin_lambda():
    api = _sls("services/api")
    eventos = [e for f in api["functions"].values() for e in f.get("events", [])]
    rutas = [e["httpApi"] if isinstance(e.get("httpApi"), str) else f'{e["httpApi"]["method"]} {e["httpApi"]["path"]}'
             for e in eventos if "httpApi" in e]
    assert all(r.split(" ", 1)[1].startswith("/api/") for r in rutas), "Solo /api/* puede llegar a una Lambda"
    integraciones = [r for r in api["resources"]["Resources"].values() if r["Type"] == "AWS::ApiGatewayV2::Integration"]
    assert integraciones and all(i["Properties"]["IntegrationType"] == "HTTP_PROXY" for i in integraciones)


def _tareas(definicion):
    """Todos los estados Task (incluidos los de dentro de un Map)."""
    for nombre, estado in (definicion.get("States") or {}).items():
        if estado.get("Type") == "Task":
            yield nombre, estado
        if estado.get("Type") == "Map":
            yield from _tareas(estado.get("ItemProcessor") or estado.get("Iterator") or {})


@pytest.mark.parametrize("maquina", ["incidente-colectivo", "escenario", "recurrencia"])
def test_step_functions_solo_llaman_al_motor_y_esperan_si_esta_ocupado(maquina):
    sys.path.insert(0, str(RAIZ / "workflows" / "src"))
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    motor = importlib.import_module("motor")
    d = yaml.load((RAIZ / "workflows" / "statemachines" / f"{maquina}.yml").read_text(encoding="utf-8"), Loader=_Cargador)
    for nombre, t in _tareas(d):
        recurso = t["Resource"]
        if isinstance(recurso, str):   # integración directa (p. ej. SNS): no usa Lambda
            assert not recurso.startswith("arn:aws:lambda"), nombre
            continue
        assert recurso["Fn::GetAtt"][0] == "detector", f"{maquina}.{nombre} llama a otra Lambda"
        assert t["Parameters"]["accion"] in motor.PASOS, f"{maquina}.{nombre}: acción desconocida"
        primero = t["Retry"][0]
        assert primero["ErrorEquals"] == ["Lambda.TooManyRequestsException"] and primero["MaxAttempts"] >= 20, nombre
    texto = (RAIZ / "workflows" / "statemachines" / f"{maquina}.yml").read_text(encoding="utf-8")
    assert not re.search(r"MaxConcurrency: (?:[2-9]|\d{2,})", texto), "Los Map deben avanzar de a uno"
