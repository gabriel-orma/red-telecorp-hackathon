"""Entorno de pruebas del detector: DynamoDB/SQS/SNS/SSM simulados con moto, con las tablas creadas a partir de
`services/base/serverless.yml` (el esquema de las pruebas es el real). Se omiten si moto o pyyaml no están instalados.

    pip install pytest "moto[dynamodb,sqs,sns,ssm]" pyyaml   &&   pytest workflows
"""
import os
import pathlib

import pytest

pytest.importorskip("moto")
yaml = pytest.importorskip("yaml")
import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

os.environ.update(
    AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing", AWS_SESSION_TOKEN="testing",
    AWS_DEFAULT_REGION="us-east-1", AWS_REGION="us-east-1", STAGE="test",
    MAQUINA_COLECTIVO="arn:aws:states:us-east-1:123456789012:stateMachine:test",
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
TABLAS = {"incidencias": "TablaIncidencias", "historial": "TablaHistorial", "metricas": "TablaMetricas",
          "antenas": "TablaAntenas", "colectivos": "TablaColectivos", "estadisticas": "TablaEstadisticas",
          "dedup": "TablaDedup"}


class _Cargador(yaml.SafeLoader):
    pass


_Cargador.add_multi_constructor("!", lambda l, s, n: l.construct_scalar(n) if isinstance(n, yaml.ScalarNode)
                                else (l.construct_sequence(n) if isinstance(n, yaml.SequenceNode) else l.construct_mapping(n)))


def cargar_yaml(ruta):
    with open(RAIZ / ruta, encoding="utf-8") as f:
        return yaml.load(f, Loader=_Cargador)


class SFNFalso:
    """Registra las ejecuciones; `fallar` simula un StartExecution caído."""

    def __init__(self):
        self.llamadas, self.fallar = [], False

    def start_execution(self, **kw):
        if self.fallar:
            raise RuntimeError("StartExecution falló (simulado)")
        self.llamadas.append(kw)
        return {"executionArn": f"arn:aws:states:us-east-1:123456789012:execution:test:{kw['name']}"}

    @property
    def nombres(self):
        return {c["name"] for c in self.llamadas}


@pytest.fixture()
def aws(monkeypatch):
    with mock_aws():
        recursos = cargar_yaml("services/base/serverless.yml")["resources"]["Resources"]
        ddb = boto3.client("dynamodb")
        for logico, rec in TABLAS.items():
            p = recursos[rec]["Properties"]
            kw = dict(TableName=f"t-{logico}", AttributeDefinitions=p["AttributeDefinitions"], KeySchema=p["KeySchema"],
                      BillingMode="PAY_PER_REQUEST")
            if "GlobalSecondaryIndexes" in p:
                kw["GlobalSecondaryIndexes"] = [{"IndexName": g["IndexName"], "KeySchema": g["KeySchema"],
                                                 "Projection": g["Projection"]} for g in p["GlobalSecondaryIndexes"]]
            ddb.create_table(**kw)
            os.environ[f"TABLA_{logico.upper()}"] = f"t-{logico}"
        os.environ["TOPICO_AVISOS"] = boto3.client("sns").create_topic(Name="avisos")["TopicArn"]
        boto3.client("ssm").put_parameter(Name="/telecorp/test/reglas", Type="String",
                                          Value=recursos["ParametroReglas"]["Properties"]["Value"].replace("\n", " "))
        from telecorp import config
        config._cache.clear()
        import comun_colectivos as cc
        sfn = SFNFalso()
        monkeypatch.setattr(cc, "_sfn", sfn)
        yield sfn


# ---------------- ayudas de datos ----------------
def tabla(nombre):
    from telecorp import db
    return db.tabla(nombre)


def item_incidencia(usuario, zona="ZONA-05", creada=None, tipo="SIN_INTERNET", estado="REGISTRADA", _n=[0]):
    """Ítem de `incidencias` tal como lo deja el worker `registrar`."""
    from telecorp import util
    _n[0] += 1
    creada = creada or util.ahora_iso()
    rep = {"usuarioId": usuario, "numeroServicio": "999111222", "zonaId": zona, "fechaHoraIncidente": creada, "tipo": tipo,
           "descripcion": "sin servicio", "email": f"{usuario}@example.com"}
    return {"incidenciaId": f"INC-R{_n[0]:06d}", "estado": estado, "creadaEn": creada, "actualizadaEn": creada,
            "zonaId": zona, "usuarioId": usuario, "tipo": tipo, "reporte": rep}


def insertar(item):
    from telecorp import util
    tabla("incidencias").put_item(Item=util.a_dynamo(item))
    return item


def colectivos():
    return tabla("colectivos").scan()["Items"]


def historial_de(entidad_id):
    from boto3.dynamodb.conditions import Key
    return tabla("historial").query(KeyConditionExpression=Key("entidadId").eq(entidad_id))["Items"]
