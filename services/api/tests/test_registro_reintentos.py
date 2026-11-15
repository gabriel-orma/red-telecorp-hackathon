"""Reportes simultáneos del mismo colectivo chocan en la transacción (TransactionConflict). Antes el mensaje volvía a SQS y
tardaba la visibilidad completa de la cola (180 s) en registrarse (medido en AWS real el 14-nov-2026). Ahora se reintenta
YA dentro de la Lambda y, si aun así falla, vuelve a la cola con espera corta."""
import json
import os
import pathlib
import sys

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("STAGE", "test")
os.environ.setdefault("COLA_REPORTES_URL", "http://cola.local/reportes")

import incidencias  # noqa: E402


def conflicto():
    return ClientError({"Error": {"Code": "TransactionCanceledException", "Message": "x"},
                        "CancellationReasons": [{"Code": "None"}, {"Code": "TransactionConflict"}]}, "TransactWriteItems")


def permanente():
    return ClientError({"Error": {"Code": "TransactionCanceledException", "Message": "x"},
                        "CancellationReasons": [{"Code": "ConditionalCheckFailed"}]}, "TransactWriteItems")


@pytest.fixture(autouse=True)
def sin_esperas(monkeypatch):
    monkeypatch.setattr(incidencias.time, "sleep", lambda s: None)


def test_solo_los_errores_transitorios_se_reintentan():
    assert incidencias._es_transitorio(conflicto())
    assert incidencias._es_transitorio(ClientError({"Error": {"Code": "ThrottlingException"}}, "Query"))
    assert not incidencias._es_transitorio(permanente())            # una condición que falla de verdad no mejora al repetir
    assert not incidencias._es_transitorio(ValueError("x"))


def test_un_choque_de_transaccion_se_resuelve_dentro_de_la_lambda(monkeypatch):
    intentos = []

    def registrar(m):
        intentos.append(1)
        if len(intentos) < 3:
            raise conflicto()
    monkeypatch.setattr(incidencias, "_registrar_incidencia", registrar)
    monkeypatch.setattr(incidencias, "_confirmar_dedup", lambda rep, iid: None)
    visibilidad = []
    monkeypatch.setattr(incidencias, "_reintentar_pronto", lambda r: visibilidad.append(r))
    ev = {"Records": [{"messageId": "m1", "receiptHandle": "h", "body": json.dumps({"incidenciaId": "INC-1", "reporte": {}})}]}
    assert incidencias.registrar(ev, None) == {"batchItemFailures": []}
    assert len(intentos) == 3 and visibilidad == []                  # nunca llegó a la cola de reintentos


def test_si_el_choque_persiste_el_mensaje_vuelve_a_la_cola_con_espera_corta(monkeypatch):
    monkeypatch.setattr(incidencias, "_registrar_incidencia", lambda m: (_ for _ in ()).throw(conflicto()))
    llamadas = []

    class Sqs:
        def change_message_visibility(self, **kw):
            llamadas.append(kw)
    monkeypatch.setattr(incidencias, "_sqs", Sqs())
    ev = {"Records": [{"messageId": "m1", "receiptHandle": "h1", "attributes": {"ApproximateReceiveCount": "2"},
                       "body": json.dumps({"incidenciaId": "INC-1", "reporte": {}})}]}
    assert incidencias.registrar(ev, None) == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
    assert llamadas == [{"QueueUrl": "http://cola.local/reportes", "ReceiptHandle": "h1", "VisibilityTimeout": 15}]   # 2.º intento → 15 s


@pytest.mark.parametrize("recibido, espera", [(1, 5), (2, 15), (3, 45), (4, 90), (5, 90)])
def test_la_espera_crece_pero_nunca_pasa_de_90_s(monkeypatch, recibido, espera):
    llamadas = []

    class Sqs:
        def change_message_visibility(self, **kw):
            llamadas.append(kw["VisibilityTimeout"])
    monkeypatch.setattr(incidencias, "_sqs", Sqs())
    incidencias._reintentar_pronto({"receiptHandle": "h", "attributes": {"ApproximateReceiveCount": str(recibido)}})
    assert llamadas == [espera]


def test_acortar_la_visibilidad_nunca_rompe_el_procesamiento(monkeypatch):
    class Sqs:
        def change_message_visibility(self, **kw):
            raise RuntimeError("sin permiso")
    monkeypatch.setattr(incidencias, "_sqs", Sqs())
    incidencias._reintentar_pronto({"receiptHandle": "h"})            # no lanza


def test_el_historial_publico_no_muestra_el_comentario_del_operador(monkeypatch):
    items = [{"entidadId": "INC-1", "sk": "a", "actor": "operador:abc-123", "tipoEvento": "CAMBIO_ESTADO",
              "detalle": "llamar a Juan al 999111222", "estadoNuevo": "EN_REVISION"},
             {"entidadId": "INC-1", "sk": "b", "actor": "SISTEMA", "tipoEvento": "CREADO", "detalle": "Reporte recibido"}]

    class T:
        def query(self, **kw):
            return {"Items": [dict(i) for i in items]}
    monkeypatch.setattr(incidencias.db, "tabla", lambda n: T())
    publico = incidencias._historial("INC-1", operador=False)
    assert publico[0]["actor"] == "OPERADOR" and publico[0]["detalle"] == "" and publico[0]["estadoNuevo"] == "EN_REVISION"
    assert publico[1]["detalle"] == "Reporte recibido"                 # lo del sistema sigue visible
    assert incidencias._historial("INC-1", operador=True)[0]["detalle"] == "llamar a Juan al 999111222"   # el operador lo ve
