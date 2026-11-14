"""Genera reportes de usuarios ficticios contra el API desplegado (para pruebas y la demo).

Desde E3.5 reportar exige cuenta: el script crea (o reutiliza) usuarios demo en Cognito
(demo.<dni>@example.com, auto-confirmados) e inicia sesión con cada uno antes de reportar.
Cognito SignUp/InitiateAuth son APIs públicas: no hacen falta credenciales de AWS.

Uso:
  python scripts/demo/reportar.py <URL> --zona ZONA-05 --n 12
  python scripts/demo/reportar.py <URL> --aleatorio --n 30
"""
import argparse
import json
import math
import random
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import boto3
from botocore import UNSIGNED
from botocore.config import Config

DESCRIPCIONES = {
    "SIN_INTERNET": ["No cargan páginas desde hace un rato", "Los datos móviles no funcionan", "Sin Internet en toda la casa"],
    "INTERNET_LENTO": ["El Internet está muy lento", "Los videos no cargan"],
    "SIN_LLAMADAS": ["No puedo hacer llamadas", "Las llamadas se cortan al instante"],
    "SIN_SENAL": ["El celular dice 'sin servicio'", "No tengo señal"],
    "INTERMITENCIA": ["La conexión va y viene", "Se corta cada pocos minutos"],
}
CLAVE_DEMO = "Demo-12345"


def pedir(url, metodo="GET", cuerpo=None, token=None):
    headers = {"content-type": "application/json", **({"authorization": token} if token else {})}
    req = urllib.request.Request(url, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo else None, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def punto_en_zona(z, rng):
    ang, dist = rng.uniform(0, 2 * math.pi), z["radioM"] * math.sqrt(rng.random()) * 0.85
    lat = z["centro"]["lat"] + dist * math.sin(ang) / 111320
    lng = z["centro"]["lng"] + dist * math.cos(ang) / (111320 * math.cos(math.radians(z["centro"]["lat"])))
    return {"lat": round(lat, 6), "lng": round(lng, 6)}


def token_demo(cognito, client_id, dni, zona_id):
    email = f"demo.{dni}@example.com"
    try:
        cognito.sign_up(ClientId=client_id, Username=email, Password=CLAVE_DEMO, UserAttributes=[
            {"Name": "name", "Value": f"Usuario Demo {dni[-3:]}"}, {"Name": "custom:dni", "Value": dni},
            {"Name": "custom:numeroServicio", "Value": f"9{dni}"}, {"Name": "custom:zonaId", "Value": zona_id},
            {"Name": "custom:avisosEmail", "Value": "0"}])
    except cognito.exceptions.UsernameExistsException:
        pass
    r = cognito.initiate_auth(ClientId=client_id, AuthFlow="USER_PASSWORD_AUTH",
                              AuthParameters={"USERNAME": email, "PASSWORD": CLAVE_DEMO})
    return r["AuthenticationResult"]["IdToken"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # consola de Windows
    p = argparse.ArgumentParser()
    p.add_argument("url", help="URL base del centro de control (sin /api)")
    p.add_argument("--zona", help="zonaId (ej. ZONA-05)")
    p.add_argument("--aleatorio", action="store_true", help="repartir entre todas las zonas")
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--semilla", type=int, default=None)
    a = p.parse_args()
    if not a.zona and not a.aleatorio:
        p.error("indica --zona o --aleatorio")

    api = a.url.rstrip("/") + "/api"
    cfg = pedir(f"{api}/config")
    cognito = boto3.client("cognito-idp", region_name=cfg["region"], config=Config(signature_version=UNSIGNED))
    rng = random.Random(a.semilla)
    zonas = {z["zonaId"]: z for z in pedir(f"{api}/zonas")["zonas"]}
    base = rng.randint(10_000_000, 89_999_999)

    def uno(i):
        z = zonas[a.zona] if a.zona else rng.choice(list(zonas.values()))
        token = token_demo(cognito, cfg["clientId"], str(base + i), z["zonaId"])
        tipo = rng.choice(list(DESCRIPCIONES))
        r = pedir(f"{api}/reportes", "POST", {"tipo": tipo, "descripcion": rng.choice(DESCRIPCIONES[tipo]),
                                              "ubicacion": punto_en_zona(z, rng)}, token)
        return z["zonaId"], r

    with ThreadPoolExecutor(8) as ex:
        resultados = list(ex.map(uno, range(a.n)))
    nuevos = sum(1 for _, r in resultados if not r.get("duplicado"))
    print(f"{nuevos}/{a.n} reportes enviados con cuentas demo (se registran vía SQS en ~1 s).")
    for zona, r in resultados[:5]:
        print(f"  {zona} → {r['incidenciaId']} ({r.get('ubicacionFuente', '')})")


if __name__ == "__main__":
    main()
