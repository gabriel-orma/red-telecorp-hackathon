"""Correo transaccional por Azure Communication Services (2.ª nube). API REST `emails:send` 2023-03-31.

Por qué existe: en el Learner Lab SES está denegado y SNS solo envía a suscriptores que confirmaron. ACS (recurso global
de Azure, permitido por la política de la suscripción) envía a cualquier destinatario que dio su consentimiento.

Autenticación: HMAC-SHA256 con la clave de acceso del recurso (firmas de ACS):
    string_to_sign = "<MÉTODO>\\n<ruta?query>\\n<x-ms-date>;<host>;<x-ms-content-sha256>"
    Authorization  = "HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256&Signature=<base64(HMAC(clave, string))>"

Límite del dominio administrado por Azure: 5/min y 10/hora. Se respeta con contadores atómicos propios (`estado.reservar_cupo`);
si se agota, `enviar_correo` devuelve `{"enviado": False, "motivo": "LIMITE"}` y el notificador usa SNS / la app.
Secreto `telecorp/<stage>/azure`: {acsEndpoint, acsKey, acsSender, mapsKey, destinatarios, limiteHora?}.
"""
import base64
import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime

from telecorp.nube2 import estado, http_cliente, secretos

API_VERSION = "2023-03-31"
SERVICIO = "azure-acs"
LIMITE_HORA_DEFECTO = 8      # el dominio administrado admite 10/h; se deja margen para pruebas manuales
LIMITE_MINUTO = 5
_DOMINIOS_RESERVADOS = ("example.com", "example.org", "example.net", "localhost")
_SUFIJOS_RESERVADOS = (".test", ".invalid", ".local", ".localhost", ".demo", ".example")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")


# ---------------------------------------------------------------- Firma (pura, con vector de prueba)
def host_de(endpoint: str) -> str:
    return re.sub(r"^https?://", "", endpoint.strip()).strip("/")


def hash_contenido(cuerpo: bytes) -> str:
    return base64.b64encode(hashlib.sha256(cuerpo).digest()).decode("ascii")


def fecha_http(ahora: datetime | None = None) -> str:
    return format_datetime((ahora or datetime.now(timezone.utc)).astimezone(timezone.utc), usegmt=True)


def firmar(metodo: str, ruta_y_query: str, host: str, cuerpo: bytes, clave_b64: str, fecha: str) -> dict:
    """Cabeceras firmadas de una petición a ACS. `clave_b64` es la clave de acceso tal como la entrega Azure (base64)."""
    contenido = hash_contenido(cuerpo)
    a_firmar = f"{metodo.upper()}\n{ruta_y_query}\n{fecha};{host};{contenido}"
    firma = base64.b64encode(hmac.new(base64.b64decode(clave_b64), a_firmar.encode("utf-8"), hashlib.sha256).digest()).decode("ascii")
    return {"x-ms-date": fecha, "x-ms-content-sha256": contenido,
            "Authorization": f"HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256&Signature={firma}"}


def cuerpo_correo(remitente: str, destinatario: str, asunto: str, texto: str, html: str | None = None) -> dict:
    contenido = {"subject": asunto[:200], "plainText": texto}
    if html:
        contenido["html"] = html
    return {"senderAddress": remitente, "content": contenido, "recipients": {"to": [{"address": destinatario}]},
            "userEngagementTrackingDisabled": True}


def destinatario_valido(email: str | None) -> bool:
    """Formato válido y dominio real: nunca se envía a dominios reservados (los reportes simulados usan example.com)."""
    if not email or not _EMAIL.match(email):
        return False
    dominio = email.rsplit("@", 1)[1].lower()
    return dominio not in _DOMINIOS_RESERVADOS and not dominio.endswith(_SUFIJOS_RESERVADOS)


def destinatario_autorizado(email: str, cfg: dict) -> bool:
    """Lista de destinatarios autorizados del secreto (`destinatarios`: correos exactos o dominios `@dominio`). SIN lista no se
    envía: las cuentas se auto-verifican en Cognito (D9), así que sin esta barrera cualquiera podría hacer que el remitente
    escriba a un tercero. En producción se exigiría verificar el correo."""
    lista = cfg.get("destinatarios")
    if not isinstance(lista, list) or not lista:
        return False
    e = str(email).strip().lower()
    return any(e == str(x).strip().lower() or (str(x).startswith("@") and e.endswith(str(x).strip().lower())) for x in lista)


# ---------------------------------------------------------------- Operaciones
def _config() -> dict | None:
    s = secretos.leer("azure")
    if s and all(s.get(k) for k in ("acsEndpoint", "acsKey", "acsSender")):
        return s
    return None


def _llamar(cfg: dict, metodo: str, ruta: str, cuerpo=None, timeout: float = 8.0):
    host = host_de(cfg["acsEndpoint"])
    datos = b"" if cuerpo is None else json.dumps(cuerpo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cab = firmar(metodo, ruta, host, datos, cfg["acsKey"], fecha_http())
    if cuerpo is not None:
        cab["Content-Type"] = "application/json"
    return http_cliente.pedir(metodo, f"https://{host}{ruta}", cab, datos if cuerpo is not None else None, timeout)


def enviar_correo(destinatario: str, asunto: str, texto: str, html: str | None = None) -> dict:
    """Envía un correo. NUNCA lanza: devuelve {enviado, motivo, operationId, estado, latenciaMs}.

    motivo ∈ {None, "NO_CONFIGURADA", "DESTINATARIO_INVALIDO", "NO_AUTORIZADO", "DISYUNTOR", "LIMITE", "CLAVE_INVALIDA", "RED", "HTTP_<n>"}.
    """
    inicio = time.time()
    try:
        cfg = _config()
        if not cfg:
            estado.anotar(SERVICIO, False, estado="NO_CONFIGURADA")
            return {"enviado": False, "motivo": "NO_CONFIGURADA"}
        if not destinatario_valido(destinatario):
            return {"enviado": False, "motivo": "DESTINATARIO_INVALIDO"}
        if not destinatario_autorizado(destinatario, cfg):
            return {"enviado": False, "motivo": "NO_AUTORIZADO"}
        if estado.disyuntor_abierto(SERVICIO):
            return {"enviado": False, "motivo": "DISYUNTOR"}
        limite_hora = int(cfg.get("limiteHora", LIMITE_HORA_DEFECTO))
        # Primero el cupo corto: una ráfaga rechazada por minuto no debe gastar el cupo de la hora.
        if not (estado.reservar_cupo("acs-min", LIMITE_MINUTO, 60) and estado.reservar_cupo("acs-hora", limite_hora, 3600)):
            return {"enviado": False, "motivo": "LIMITE"}
        try:
            base64.b64decode(cfg["acsKey"], validate=True)
        except Exception:  # noqa: BLE001
            estado.anotar(SERVICIO, False, error="CLAVE_INVALIDA", cuenta=False)   # no se llegó a llamar a Azure
            return {"enviado": False, "motivo": "CLAVE_INVALIDA"}
        cuerpo = cuerpo_correo(cfg["acsSender"], destinatario, asunto, texto, html)
        st, cab, datos = _llamar(cfg, "POST", f"/emails:send?api-version={API_VERSION}", cuerpo)
        ms = int((time.time() - inicio) * 1000)
        if st == 202:
            operacion = cab.get("operation-id") or (http_cliente.como_json(datos) or {}).get("id")
            estado.registrar_exito(SERVICIO)
            estado.anotar(SERVICIO, True, ms)
            return {"enviado": True, "motivo": None, "operationId": operacion, "estado": "Running", "latenciaMs": ms}
        codigo = http_cliente.codigo_error(datos)
        estado.registrar_fallo(SERVICIO)
        estado.anotar(SERVICIO, False, ms, error=f"HTTP_{st} {codigo}".strip())
        return {"enviado": False, "motivo": f"HTTP_{st}", "detalle": codigo, "latenciaMs": ms}
    except http_cliente.ErrorNube as e:
        estado.registrar_fallo(SERVICIO)
        estado.anotar(SERVICIO, False, error=e.codigo)
        return {"enviado": False, "motivo": e.codigo}
    except Exception as e:  # noqa: BLE001 - jamás se propaga al flujo del negocio
        print(f"azure_acs: error inesperado ({type(e).__name__})")
        return {"enviado": False, "motivo": "ERROR"}


def consultar_operacion(operation_id: str) -> dict:
    """Estado de un envío: {estado: NotStarted|Running|Succeeded|Failed|Canceled, error?}. None-safe."""
    try:
        cfg = _config()
        if not cfg:
            return {"estado": None, "motivo": "NO_CONFIGURADA"}
        st, _, datos = _llamar(cfg, "GET", f"/emails/operations/{operation_id}?api-version={API_VERSION}")
        j = http_cliente.como_json(datos) or {}
        return {"estado": j.get("status"), "http": st, "error": (j.get("error") or {}).get("code")}
    except Exception as e:  # noqa: BLE001
        return {"estado": None, "motivo": type(e).__name__}


def sondear() -> dict:
    """Comprueba credenciales SIN enviar correo: `emails:send` con la lista de destinatarios VACÍA. ACS autentica primero y
    valida después: con la clave buena responde 400 BadRequest (~1 s, no crea operación ni envía nada); con clave o firma
    malas, 401. (Consultar una operación inexistente no sirve: Azure tarda ~30 s y responde 504; medido el 14-nov-2026.)"""
    inicio = time.time()
    try:
        cfg = _config()
        if not cfg:
            estado.anotar(SERVICIO, False, estado="NO_CONFIGURADA")
            return {"ok": False, "motivo": "NO_CONFIGURADA"}
        cuerpo = {"senderAddress": cfg["acsSender"], "content": {"subject": "sonda", "plainText": "sonda"}, "recipients": {"to": []}}
        st, _, _ = _llamar(cfg, "POST", f"/emails:send?api-version={API_VERSION}", cuerpo, timeout=6.0)
        ok = st == 400
        ms = int((time.time() - inicio) * 1000)
        estado.anotar(SERVICIO, ok, ms, error=None if ok else f"HTTP_{st}")
        return {"ok": ok, "http": st, "latenciaMs": ms}
    except Exception as e:  # noqa: BLE001
        estado.anotar(SERVICIO, False, error=getattr(e, "codigo", type(e).__name__))
        return {"ok": False, "motivo": type(e).__name__}
