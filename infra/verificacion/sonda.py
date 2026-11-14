"""Sonda de E0: prueba, con los permisos de LabRole, cada servicio que usará la plataforma."""
import json
import os
import time

import boto3


def _probar(nombre, fn, resultados):
    try:
        detalle = fn()
        resultados[nombre] = {"ok": True, "detalle": detalle}
    except Exception as e:  # noqa: BLE001 - queremos el error tal cual para el reporte
        resultados[nombre] = {"ok": False, "detalle": f"{type(e).__name__}: {e}"[:300]}


def sonda(event, context):
    r = {}
    ddb = boto3.client("dynamodb")
    _probar("dynamodb", lambda: ddb.put_item(TableName=os.environ["TABLA"], Item={"pk": {"S": "x"}, "expira": {"N": str(int(time.time()) + 600)}}) and "put ok", r)
    _probar("sqs", lambda: boto3.client("sqs").send_message(QueueUrl=os.environ["COLA"], MessageBody="{}")["MessageId"], r)
    sns = boto3.client("sns")
    _probar("sns_topico", lambda: sns.publish(TopicArn=os.environ["TOPICO"], Message="humo")["MessageId"], r)
    _probar("sns_sms_atributos", lambda: sns.get_sms_attributes(), r)
    _probar("sns_sms_sandbox", lambda: sns.get_sms_sandbox_account_status(), r)
    ses = boto3.client("ses")
    _probar("ses_cuota", lambda: ses.get_send_quota(), r)
    _probar("ses_identidades", lambda: ses.list_identities(MaxItems=5)["Identities"], r)
    _probar("secretsmanager", lambda: json.loads(boto3.client("secretsmanager").get_secret_value(SecretId=os.environ["SECRETO"])["SecretString"]), r)
    _probar("ssm", lambda: boto3.client("ssm").get_parameter(Name=os.environ["PARAMETRO"])["Parameter"]["Value"], r)
    _probar("s3", lambda: boto3.client("s3").put_object(Bucket=os.environ["BUCKET"], Key="index.html", Body=b"<h1>Red TeleCorp: humo OK</h1>", ContentType="text/html") and "put ok", r)
    _probar("stepfunctions", lambda: boto3.client("stepfunctions").start_execution(stateMachineArn=os.environ["MAQUINA"], input=json.dumps({"items": [1, 2, 3]}))["executionArn"], r)
    _probar("bedrock", lambda: [m["modelId"] for m in boto3.client("bedrock").list_foundation_models()["modelSummaries"]][:5], r)
    _probar("comprehend", lambda: boto3.client("comprehend").detect_sentiment(Text="no tengo internet", LanguageCode="es")["Sentiment"], r)
    return {"statusCode": 200, "headers": {"content-type": "application/json"}, "body": json.dumps(r, default=str, indent=1)}


def eco(event, context):
    print(json.dumps(event, default=str)[:500])
    return {"ok": True}


def ws(event, context):
    return {"statusCode": 200, "body": "ws ok"}
