"""Tercera nube (decisión D15): espejo del estado público en Cloudflare Workers + KV.

Cada 5 minutos el barrido del motor `detector` (no hay Lambda nueva: D14) calcula el estado público de la red y lo
publica en un Worker de Cloudflare (`edge/estado/`), que lo guarda en KV y lo sirve desde el borde:

- la página pública del frontend lo usa como **respaldo** si `GET /api/estado` falla (AWS caído u ocupado);
- el Worker sirve además su **propia página de estado**, que sigue en línea aunque AWS no responda.

Secreto `telecorp/<stage>/cloudflare` = {url, token}: `url` del Worker (https://….workers.dev) y `token` de publicación
(el mismo que el Worker guarda como secreto `TOKEN_PUBLICACION`). Sin secreto la integración queda apagada sin romper nada.

Límite del plan gratuito de KV: 1000 escrituras al día. Una publicación = 1 escritura, y como mucho una cada
`INTERVALO_MIN_S` (cupo atómico), así que el máximo es 288 al día.
"""
import time

from telecorp import estado_red, util
from telecorp.nube2 import estado, http_cliente, secretos

SERVICIO = "cloudflare-workers"
INTERVALO_MIN_S = 240          # ≤ 360 escrituras/día aunque el barrido corra más seguido
TIMEOUT_S = 8


def _config() -> dict | None:
    cfg = secretos.leer("cloudflare")
    if cfg and str(cfg.get("url", "")).startswith("https://") and cfg.get("token"):
        return {"url": cfg["url"].rstrip("/"), "token": cfg["token"]}
    return None


def configurado() -> bool:
    return _config() is not None


def armar_publicacion(estados: dict) -> dict:
    """Cuerpo que recibe el Worker: el estado global, el de cada zona y los mensajes del semáforo."""
    return {"version": 1, "publicadoEn": util.ahora_iso(), "estados": estados}


def publicar() -> dict:
    """Publica el estado en Cloudflare. Nunca lanza: devuelve {"publicado": bool, "motivo"?: str}."""
    cfg = _config()
    if not cfg:
        estado.anotar(SERVICIO, False, estado="NO_CONFIGURADA")
        return {"publicado": False, "motivo": "SIN_CONFIGURAR"}
    if estado.disyuntor_abierto(SERVICIO):
        return {"publicado": False, "motivo": "DISYUNTOR"}
    if not estado.reservar_cupo(f"publicar-{SERVICIO}", 1, INTERVALO_MIN_S):
        return {"publicado": False, "motivo": "CUPO"}
    try:
        cuerpo = armar_publicacion(estado_red.calcular_todo())
    except Exception as e:  # noqa: BLE001 - el espejo nunca rompe el barrido
        print(f"cloudflare: no se pudo calcular el estado ({type(e).__name__})")
        return {"publicado": False, "motivo": "CALCULO"}
    inicio = time.time()
    try:
        status, _, resp = http_cliente.pedir("PUT", f"{cfg['url']}/publicar", {"Authorization": f"Bearer {cfg['token']}"},
                                             cuerpo, timeout=TIMEOUT_S)
    except http_cliente.ErrorNube as e:
        estado.registrar_fallo(SERVICIO)
        estado.anotar(SERVICIO, False, error=e.codigo)
        return {"publicado": False, "motivo": e.codigo}
    latencia = int((time.time() - inicio) * 1000)
    if status != 200:
        estado.registrar_fallo(SERVICIO)
        estado.anotar(SERVICIO, False, latencia, error=f"HTTP {status} {http_cliente.codigo_error(resp)}".strip())
        return {"publicado": False, "motivo": f"HTTP {status}"}
    estado.registrar_exito(SERVICIO)
    estado.anotar(SERVICIO, True, latencia)
    return {"publicado": True}


def sondear() -> None:
    """Sonda barata para el panel Nubes: `GET /salud` del Worker (lee KV, no escribe). Anota en el tablero."""
    cfg = _config()
    if not cfg:
        return
    inicio = time.time()
    try:
        status, _, resp = http_cliente.pedir("GET", f"{cfg['url']}/salud", timeout=TIMEOUT_S)
    except http_cliente.ErrorNube as e:
        estado.anotar(SERVICIO, False, error=e.codigo)
        return
    datos = http_cliente.como_json(resp) or {}
    ok = status == 200 and datos.get("ok") is True
    estado.anotar(SERVICIO, ok, int((time.time() - inicio) * 1000), error=None if ok else f"HTTP {status}")
