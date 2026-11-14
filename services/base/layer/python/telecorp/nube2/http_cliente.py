"""Frontera HTTP única de las integraciones (stdlib). Las pruebas reemplazan `transporte` por un doble."""
import json
import urllib.error
import urllib.request


class ErrorNube(Exception):
    """Fallo de una integración. El mensaje es seguro para logs: nunca incluye URLs con claves, cabeceras ni cuerpos."""

    def __init__(self, codigo: str, detalle: str = ""):
        super().__init__(f"{codigo}{': ' + detalle if detalle else ''}")
        self.codigo, self.detalle = codigo, detalle


def _transporte_real(metodo: str, url: str, cabeceras: dict, cuerpo: bytes | None, timeout: float):
    req = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - URLs https fijas de cada proveedor
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ErrorNube("RED", type(e).__name__) from None  # sin `e`: podría contener la URL


transporte = _transporte_real  # <- punto de sustitución en pruebas


def pedir(metodo: str, url: str, cabeceras: dict | None = None, cuerpo=None, timeout: float = 5.0):
    """Devuelve (status, cabeceras_en_minúsculas, bytes). `cuerpo` dict/list se envía como JSON."""
    cabeceras = dict(cabeceras or {})
    if isinstance(cuerpo, (dict, list)):
        cuerpo = json.dumps(cuerpo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        cabeceras.setdefault("Content-Type", "application/json")
    elif isinstance(cuerpo, str):
        cuerpo = cuerpo.encode("utf-8")
    return transporte(metodo, url, cabeceras, cuerpo, timeout)


def como_json(cuerpo: bytes):
    """JSON del cuerpo o None si no es JSON."""
    try:
        return json.loads(cuerpo.decode("utf-8")) if cuerpo else None
    except (ValueError, UnicodeDecodeError):
        return None


def codigo_error(cuerpo: bytes) -> str:
    """Código de error corto del cuerpo (formatos de Azure, Google y Gemini) o ''. No devuelve mensajes completos."""
    datos = como_json(cuerpo)
    if isinstance(datos, dict):
        err = datos.get("error")
        if isinstance(err, dict):
            return str(err.get("code") or err.get("status") or "")[:60]
        if isinstance(err, str):
            return err[:60]
    return ""
