"""Hosting HTTPS del frontend (CloudFront está bloqueado en Learner Lab; ver D1).

El build de Vite vive en un bucket S3 privado y versionado. Esta Lambda lo entrega por el HTTP API:
- /assets/* → caché inmutable de 1 año (los nombres llevan hash).
- Rutas sin extensión → index.html (SPA).
- Compresión gzip y caché en memoria entre invocaciones (la Lambda caliente responde sin leer S3).
"""
import base64
import gzip
import mimetypes
import os
import time

import boto3

_s3 = boto3.client("s3")
_cache: dict = {}
_TEXTO = ("text/", "application/javascript", "application/json", "image/svg+xml", "application/manifest+json")
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")  # worker de maplibre (módulo)
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("font/woff2", ".woff2")


def _leer(clave: str):
    # assets/* llevan hash en el nombre → caché permanente. El resto (index.html) se refresca cada 15 s
    # para que un nuevo despliegue se vea sin reiniciar la Lambda.
    if clave in _cache and not clave.startswith("assets/") and time.time() - _cache[clave][3] > 15:
        del _cache[clave]
    if clave not in _cache:
        try:
            obj = _s3.get_object(Bucket=os.environ["BUCKET_FRONTEND"], Key=clave)
        except _s3.exceptions.NoSuchKey:
            return None
        cuerpo = obj["Body"].read()
        tipo = mimetypes.guess_type(clave)[0] or "application/octet-stream"
        comprimible = tipo.startswith(_TEXTO) and len(cuerpo) > 1024
        _cache[clave] = (gzip.compress(cuerpo, 6) if comprimible else cuerpo, tipo, comprimible, time.time())
    return _cache[clave][:3]


def handler(event, context):
    ruta = event.get("rawPath", "/").lstrip("/")
    if not ruta or "." not in ruta.rsplit("/", 1)[-1]:
        ruta = "index.html"
    archivo = _leer(ruta)
    if archivo is None and ruta.startswith("assets/"):
        return {"statusCode": 404, "headers": {"content-type": "text/plain"}, "body": "No encontrado"}
    if archivo is None:
        archivo, ruta = _leer("index.html"), "index.html"
        if archivo is None:
            return {"statusCode": 503, "headers": {"content-type": "text/plain; charset=utf-8"},
                    "body": "Frontend no publicado todavía. Ejecuta: bash scripts/deploy.sh <stage>"}
    cuerpo, tipo, comprimido = archivo
    headers = {
        "content-type": tipo + ("; charset=utf-8" if tipo.startswith("text/") else ""),
        "cache-control": "public, max-age=31536000, immutable" if ruta.startswith("assets/") else "no-cache",
        "x-content-type-options": "nosniff",
    }
    if comprimido:
        headers["content-encoding"] = "gzip"
    return {"statusCode": 200, "headers": headers, "isBase64Encoded": True,
            "body": base64.b64encode(cuerpo).decode("ascii")}
