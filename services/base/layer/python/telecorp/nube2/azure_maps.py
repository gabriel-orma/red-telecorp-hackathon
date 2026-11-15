"""Azure Maps (2.ª nube): clima, geocodificación inversa y alertas severas por coordenadas.

Los tres endpoints se verificaron contra la API real con la clave del recurso (Maps Gen2, ubicación global):
  GET /weather/currentConditions/json?api-version=1.1&query=<lat>,<lon>
  GET /reverseGeocode?api-version=2023-06-01&coordinates=<lon>,<lat>
  GET /weather/severe/alerts/json?api-version=1.1&query=<lat>,<lon>
Autenticación: clave compartida (`subscription-key`) del secreto `telecorp/<stage>/azure` → `mapsKey`.

Contrato: ante CUALQUIER fallo devuelven None (el análisis sigue con sus reglas y simplemente sin clima).
La URL lleva la clave: nunca se registra ni se incluye en un error.
"""
import time
import urllib.parse

from telecorp.nube2 import estado, http_cliente, secretos

BASE = "https://atlas.microsoft.com"
SERVICIO = "azure-maps"
TTL_CACHE_SEGUNDOS = 600
TIMEOUT_SEGUNDOS = 5.0
_cache: dict = {}


# ---------------------------------------------------------------- Parseo (puro)
def parsear_clima(datos) -> dict | None:
    try:
        r = datos["results"][0]
        return {"fuente": "AzureMaps", "frase": str(r.get("phrase") or "")[:80],
                "temperaturaC": float(r["temperature"]["value"]), "precipitacion": bool(r.get("hasPrecipitation")),
                "vientoKmH": float(r["wind"]["speed"]["value"])}
    except (KeyError, IndexError, TypeError, ValueError):
        return None


# ---------------------------------------------------------------- Llamadas
def _clave() -> str | None:
    s = secretos.leer("azure")
    return (s or {}).get("mapsKey") or None


def _get(clave_cache: tuple, ruta: str, parametros: dict, parser):
    ahora = time.time()
    if clave_cache in _cache and _cache[clave_cache][0] > ahora:
        return _cache[clave_cache][1]
    inicio = time.time()
    try:
        clave = _clave()
        if not clave:
            estado.anotar(SERVICIO, False, estado="NO_CONFIGURADA")
            return None
        if estado.disyuntor_abierto(SERVICIO):
            return None
        url = f"{BASE}{ruta}?{urllib.parse.urlencode({**parametros, 'subscription-key': clave}, safe=',')}"
        st, _, cuerpo = http_cliente.pedir("GET", url, {"Accept": "application/json"}, timeout=TIMEOUT_SEGUNDOS)
        ms = int((time.time() - inicio) * 1000)
        if st != 200:
            estado.registrar_fallo(SERVICIO)
            estado.anotar(SERVICIO, False, ms, error=f"HTTP_{st}")
            return None
        resultado = parser(http_cliente.como_json(cuerpo))
        if resultado is None:
            estado.anotar(SERVICIO, False, ms, error="RESPUESTA_INESPERADA")
            return None
        estado.registrar_exito(SERVICIO)
        estado.anotar(SERVICIO, True, ms)
        _cache[clave_cache] = (ahora + TTL_CACHE_SEGUNDOS, resultado)
        return resultado
    except http_cliente.ErrorNube as e:
        estado.registrar_fallo(SERVICIO)
        estado.anotar(SERVICIO, False, error=e.codigo)
        return None
    except Exception as e:  # noqa: BLE001
        print(f"azure_maps: error inesperado ({type(e).__name__})")
        return None


def clima_actual(lat: float, lon: float, idioma: str | None = None) -> dict | None:
    """{fuente, frase, temperaturaC, precipitacion, vientoKmH} o None. `idioma` p. ej. "es-ES" (opcional)."""
    p = {"api-version": "1.1", "query": f"{float(lat):.4f},{float(lon):.4f}"}
    if idioma:
        p["language"] = idioma
    return _get(("clima", round(lat, 2), round(lon, 2), idioma), "/weather/currentConditions/json", p, parsear_clima)

