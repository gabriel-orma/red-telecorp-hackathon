"""Publica frontend/dist en el bucket del frontend con los encabezados que antes ponía la Lambda `web` (decisión D14).

El HTTP API entrega los archivos tal cual los guarda S3, así que aquí se fijan:
- Content-Type correcto (incluido .mjs, el worker de MapLibre, que debe ser JavaScript).
- Cache-Control: assets con hash → 1 año, inmutable; index.html y el resto → sin caché (un despliegue se ve al instante).
- Content-Encoding gzip para texto (JS, CSS, SVG, HTML): ~4 veces menos datos.
- Borra los archivos que ya no existen en dist/ (el bucket es versionado: quedan 7 días como versión anterior).

Uso: python scripts/publicar-frontend.py <bucket>
"""
import gzip
import mimetypes
import os
import sys

import boto3

mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/javascript", ".mjs")
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("image/svg+xml", ".svg")
COMPRIMIBLE = ("text/", "image/svg+xml", "application/json")


def main(bucket: str, raiz: str = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")) -> None:
    s3 = boto3.client("s3", region_name="us-east-1")
    raiz = os.path.abspath(raiz)
    publicadas = set()
    for carpeta, _, archivos in os.walk(raiz):
        for nombre in archivos:
            ruta = os.path.join(carpeta, nombre)
            clave = os.path.relpath(ruta, raiz).replace(os.sep, "/")
            tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
            cuerpo = open(ruta, "rb").read()
            extra = {
                "ContentType": tipo + ("; charset=utf-8" if tipo.startswith("text/") else ""),
                "CacheControl": "public, max-age=31536000, immutable" if clave.startswith("assets/") else "no-cache",
            }
            if tipo.startswith(COMPRIMIBLE) and len(cuerpo) > 1024:
                cuerpo = gzip.compress(cuerpo, 9)
                extra["ContentEncoding"] = "gzip"
            s3.put_object(Bucket=bucket, Key=clave, Body=cuerpo, **extra)
            publicadas.add(clave)
    viejas = [o["Key"] for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket) for o in p.get("Contents", [])
              if o["Key"] not in publicadas]
    for i in range(0, len(viejas), 1000):
        s3.delete_objects(Bucket=bucket, Delete={"Objects": [{"Key": k} for k in viejas[i:i + 1000]], "Quiet": True})
    print(f"  {len(publicadas)} archivos publicados, {len(viejas)} borrados")


if __name__ == "__main__":
    main(sys.argv[1])
