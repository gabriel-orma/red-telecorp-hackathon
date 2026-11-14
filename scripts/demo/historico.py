"""Siembra 7 días de contadores históricos (DATOS DE DEMO) en la tabla `estadisticas`.

Sirve para que la página pública de estado tenga una "línea base" con forma realista
(madrugada tranquila, picos en la mañana y la noche) antes de la demo. Suma con ADD:
**ejecútalo una sola vez por stage** (o después de `scripts/remove.sh`).

Uso (requiere credenciales de AWS):
  python scripts/demo/historico.py dev-gabriel
"""
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import boto3

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TIPOS = {"SIN_INTERNET": 0.34, "INTERNET_LENTO": 0.24, "INTERMITENCIA": 0.16, "SIN_SENAL": 0.12, "SIN_LLAMADAS": 0.09, "SIN_SMS": 0.03, "OTRO": 0.02}


def actividad(hora_lima: float) -> float:
    """Curva diaria de reportes (0–1): baja de madrugada, pico a media mañana y en la noche."""
    manana = math.exp(-((hora_lima - 10) ** 2) / 6)
    noche = 0.8 * math.exp(-((hora_lima - 20.5) ** 2) / 5)
    return 0.08 + manana + noche


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: python scripts/demo/historico.py <stage>")
    stage = sys.argv[1]
    tabla = boto3.resource("dynamodb", region_name="us-east-1").Table(f"telecorp-{stage}-estadisticas")
    zonas = json.load(open(os.path.join(RAIZ, "contracts", "zonas.json"), encoding="utf-8"))["zonas"]
    total_clientes = sum(z["clientesEstimados"] for z in zonas)
    rng = random.Random(42)

    ahora = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    fin = ahora - timedelta(minutes=ahora.minute % 15) - timedelta(hours=1)  # deja libre la última hora
    t = fin - timedelta(days=8)
    ttl = int(time.time()) + 35 * 86400
    operaciones = []
    while t < fin:
        hora_lima = ((t.hour - 5) % 24) + t.minute / 60
        b = t.strftime("%Y-%m-%dT%H:%M:00Z")
        for z in zonas:
            esperado = 2.2 * actividad(hora_lima) * z["clientesEstimados"] / total_clientes * len(zonas) / 4
            n = sum(1 for _ in range(6) if rng.random() < esperado / 6)  # ~Poisson acotado
            for _ in range(n):
                tipo = rng.choices(list(TIPOS), weights=list(TIPOS.values()))[0]
                operaciones.append((z["zonaId"], b, tipo))
        t += timedelta(minutes=15)

    def sumar(op):
        zona, b, tipo = op
        for serie in ("GLOBAL", zona):
            tabla.update_item(Key={"serie": serie, "bucket": b},
                              UpdateExpression="ADD #total :uno, #tipo :uno, demo :uno SET expiraEn = if_not_exists(expiraEn, :ttl)",
                              ExpressionAttributeNames={"#total": "total", "#tipo": f"t_{tipo}"},
                              ExpressionAttributeValues={":uno": 1, ":ttl": ttl})

    print(f"Sembrando {len(operaciones)} reportes históricos de demo (8 días) en telecorp-{stage}-estadisticas…")
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(sumar, operaciones))
    print("Listo. Los ítems quedan marcados con el atributo `demo`.")


if __name__ == "__main__":
    main()
