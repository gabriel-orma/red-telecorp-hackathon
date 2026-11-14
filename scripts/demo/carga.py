"""Prueba de carga (E5): una avalancha de reportes por el camino real (API Gateway → SQS → worker) sin perder ninguno.

- Crea (o reutiliza) U usuarios demo en Cognito y cada uno reporta en Z zonas distintas → U×Z reportes únicos
  (la deduplicación es por usuario+zona, así que ninguno se descarta).
- Los envía con alta concurrencia y mide la aceptación (202).
- Espera a que el worker los registre y verifica que TODOS existan, y que la DLQ de reportes esté vacía.

Uso (requiere credenciales de AWS solo para leer la DLQ):
  python scripts/demo/carga.py <URL> --stage dev-gabriel --usuarios 40 --concurrencia 40
"""
import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore import UNSIGNED
from botocore.config import Config

sys.path.insert(0, __import__("os").path.dirname(__file__))
from reportar import pedir, punto_en_zona, token_demo  # noqa: E402

TIPOS = ["SIN_INTERNET", "INTERNET_LENTO", "INTERMITENCIA", "SIN_SENAL", "SIN_LLAMADAS"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("url")
    p.add_argument("--stage", required=True)
    p.add_argument("--usuarios", type=int, default=40)
    p.add_argument("--zonas", type=int, default=12, help="zonas por usuario (máx. 12)")
    p.add_argument("--concurrencia", type=int, default=40)
    a = p.parse_args()

    api = a.url.rstrip("/") + "/api"
    cfg = pedir(f"{api}/config")
    cognito = boto3.client("cognito-idp", region_name=cfg["region"], config=Config(signature_version=UNSIGNED))
    zonas = pedir(f"{api}/zonas")["zonas"][: a.zonas]
    rng = random.Random()
    base = rng.randint(10_000_000, 89_999_999)

    print(f"Preparando {a.usuarios} usuarios demo…")
    with ThreadPoolExecutor(10) as ex:
        tokens = list(ex.map(lambda i: token_demo(cognito, cfg["clientId"], str(base + i), zonas[0]["zonaId"]), range(a.usuarios)))

    trabajos = [(t, z) for t in tokens for z in zonas]
    rng.shuffle(trabajos)
    print(f"Enviando {len(trabajos)} reportes con concurrencia {a.concurrencia}…")

    def enviar(trabajo):
        token, z = trabajo
        cuerpo = {"tipo": rng.choice(TIPOS), "descripcion": "Prueba de carga", "ubicacion": punto_en_zona(z, rng)}
        for intento in range(4):
            try:
                return pedir(f"{api}/reportes", "POST", cuerpo, token)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503) and intento < 3:
                    time.sleep(0.5 * 2 ** intento)
                    continue
                return {"error": e.code}

    t0 = time.time()
    with ThreadPoolExecutor(a.concurrencia) as ex:
        res = list(ex.map(enviar, trabajos))
    dur = time.time() - t0
    ids = [r["incidenciaId"] for r in res if r and "incidenciaId" in r and not r.get("duplicado")]
    errores = [r for r in res if not r or "error" in r]
    print(f"  aceptados: {len(ids)}/{len(trabajos)} en {dur:.1f} s ({len(trabajos) / dur:.0f} reportes/s) · errores: {len(errores)}")

    print("Esperando a que el worker registre todo…")
    pendientes, limite = set(ids), time.time() + 120
    while pendientes and time.time() < limite:
        def existe(i):
            try:
                pedir(f"{api}/incidencias/{i}")
                return i
            except urllib.error.HTTPError:
                return None
        with ThreadPoolExecutor(30) as ex:
            pendientes -= {i for i in ex.map(existe, list(pendientes)) if i}
        if pendientes:
            time.sleep(3)
    print(f"  registradas: {len(ids) - len(pendientes)}/{len(ids)} · perdidas: {len(pendientes)}")

    sqs = boto3.client("sqs", region_name=cfg["region"])
    dlq = sqs.get_queue_url(QueueName=f"telecorp-{a.stage}-reportes-dlq")["QueueUrl"]
    en_dlq = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["ApproximateNumberOfMessages"])["Attributes"]["ApproximateNumberOfMessages"]
    print(f"  mensajes en la DLQ: {en_dlq}")
    ok = not pendientes and not errores and en_dlq == "0"
    print("RESULTADO:", "OK, sin pérdidas" if ok else "REVISAR")
    print(json.dumps({"enviados": len(trabajos), "aceptados": len(ids), "registrados": len(ids) - len(pendientes),
                      "errores": len(errores), "dlq": int(en_dlq), "segundos": round(dur, 1)}))


if __name__ == "__main__":
    main()
