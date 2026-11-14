"""Genera reportes de usuarios ficticios contra el API desplegado (para pruebas y demo).

Uso:
  python scripts/demo/reportar.py <URL> --zona ZONA-05 --n 12
  python scripts/demo/reportar.py <URL> --aleatorio --n 30     # repartidos en todas las zonas

Solo usa la librería estándar. Cada reporte usa un DNI ficticio distinto (no se deduplican entre sí).
"""
import argparse
import json
import math
import random
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

DESCRIPCIONES = {
    "SIN_INTERNET": ["No cargan páginas desde hace un rato", "Los datos móviles no funcionan", "Sin Internet en toda la casa"],
    "INTERNET_LENTO": ["El Internet está muy lento", "Los videos no cargan"],
    "SIN_LLAMADAS": ["No puedo hacer llamadas", "Las llamadas se cortan al instante"],
    "SIN_SENAL": ["El celular dice 'sin servicio'", "No tengo señal"],
    "INTERMITENCIA": ["La conexión va y viene", "Se corta cada pocos minutos"],
}


def pedir(url, metodo="GET", cuerpo=None):
    req = urllib.request.Request(url, method=metodo, data=json.dumps(cuerpo).encode() if cuerpo else None,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def punto_en_zona(z, rng):
    ang, dist = rng.uniform(0, 2 * math.pi), z["radioM"] * math.sqrt(rng.random()) * 0.9
    lat = z["centro"]["lat"] + dist * math.sin(ang) / 111320
    lng = z["centro"]["lng"] + dist * math.cos(ang) / (111320 * math.cos(math.radians(z["centro"]["lat"])))
    return {"lat": round(lat, 6), "lng": round(lng, 6)}


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
    rng = random.Random(a.semilla)
    zonas = {z["zonaId"]: z for z in pedir(f"{api}/zonas")["zonas"]}
    base = rng.randint(10_000_000, 89_999_999)

    def uno(i):
        z = zonas[a.zona] if a.zona else rng.choice(list(zonas.values()))
        tipo = rng.choice(list(DESCRIPCIONES))
        reporte = {
            "usuarioId": str(base + i), "nombre": f"Usuario Demo {i + 1}",
            "numeroServicio": f"9{rng.randint(10_000_000, 99_999_999)}",
            "email": f"demo{base + i}@example.com",
            "zonaId": z["zonaId"], "ubicacion": punto_en_zona(z, rng),
            "fechaHoraIncidente": (datetime.now(timezone.utc) - timedelta(minutes=rng.randint(1, 90))).isoformat(),
            "tipo": tipo, "descripcion": rng.choice(DESCRIPCIONES[tipo]),
        }
        return z["zonaId"], pedir(f"{api}/reportes", "POST", reporte)

    with ThreadPoolExecutor(8) as ex:
        resultados = list(ex.map(uno, range(a.n)))
    nuevos = sum(1 for _, r in resultados if not r.get("duplicado"))
    print(f"{nuevos}/{a.n} reportes enviados (las incidencias se registran vía SQS en ~1 s).")
    for zona, r in resultados[:5]:
        print(f"  {zona} → {r['incidenciaId']}")


if __name__ == "__main__":
    main()
