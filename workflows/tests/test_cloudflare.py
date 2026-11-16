"""Tercera nube (D15): el barrido del motor publica el estado público en Cloudflare.

DynamoDB simulado (moto) y SOLO la frontera HTTP/Secrets sustituida: no prueba que Cloudflare responda (eso se verifica contra
el Worker real), sino qué se envía, cuándo y que un fallo de Cloudflare nunca rompe el barrido.
"""
import json

import pytest

from telecorp.nube2 import cloudflare, estado, http_cliente, secretos

from conftest import insertar, item_incidencia

URL = "https://telecorp-estado-test.ejemplo.workers.dev"


class Worker:
    def __init__(self):
        self.llamadas = []
        self.respuesta = lambda: (200, {}, b'{"ok":true}')

    def transporte(self, metodo, url, cabeceras, cuerpo, timeout):
        assert url.startswith(URL), f"salida de red inesperada: {url}"
        self.llamadas.append((metodo, url, dict(cabeceras), json.loads(cuerpo) if cuerpo else None))
        return self.respuesta()


@pytest.fixture()
def worker(aws, monkeypatch):
    w = Worker()
    monkeypatch.setattr(secretos, "leer", lambda nombre, usar_cache=True: {"url": URL + "/", "token": "tok-123"} if nombre == "cloudflare" else None)
    monkeypatch.setattr(http_cliente, "transporte", w.transporte)
    return w


def test_publica_el_estado_global_y_de_cada_zona_con_token(worker):
    insertar(item_incidencia("u1", zona="ZONA-05"))
    assert cloudflare.publicar() == {"publicado": True}
    metodo, url, cabeceras, cuerpo = worker.llamadas[0]
    assert (metodo, url) == ("PUT", f"{URL}/publicar")
    assert cabeceras["Authorization"] == "Bearer tok-123"
    # Cloudflare bloquea el User-Agent por defecto de Python (error 1010): siempre se envía uno propio.
    assert not cabeceras["User-Agent"].startswith("Python-urllib")
    assert cuerpo["version"] == 1 and "GLOBAL" in cuerpo["estados"] and "ZONA-05" in cuerpo["estados"]
    assert cuerpo["estados"]["ZONA-05"]["alcance"] == "ZONA-05"
    assert estado.leer_tablero()["cloudflare-workers"]["estado"] == "OK"


def test_como_mucho_una_publicacion_cada_4_minutos(worker):
    """Plan gratuito de KV: 1000 escrituras al día. Aunque el barrido corra más seguido, no se pasa."""
    assert cloudflare.publicar()["publicado"]
    assert cloudflare.publicar() == {"publicado": False, "motivo": "CUPO"}
    assert len(worker.llamadas) == 1


def test_sin_secreto_no_llama_a_nadie(aws, monkeypatch):
    monkeypatch.setattr(secretos, "leer", lambda nombre, usar_cache=True: None)
    monkeypatch.setattr(http_cliente, "transporte", lambda *a: pytest.fail("no debe salir a la red"))
    assert cloudflare.publicar() == {"publicado": False, "motivo": "SIN_CONFIGURAR"}
    assert not cloudflare.configurado()


def test_url_sin_https_se_considera_no_configurada(aws, monkeypatch):
    monkeypatch.setattr(secretos, "leer", lambda nombre, usar_cache=True: {"url": "http://x.workers.dev", "token": "t"})
    assert not cloudflare.configurado()


def test_un_fallo_de_cloudflare_no_rompe_el_barrido(worker):
    import detector
    worker.respuesta = lambda: (500, {}, b'{"error":"boom"}')
    r = detector.reconciliar({}, None)
    assert r["espejo"] == {"publicado": False, "motivo": "HTTP 500"}
    assert estado.leer_tablero()["cloudflare-workers"]["estado"] == "ERROR"


def test_el_barrido_del_motor_publica(worker):
    import motor
    r = motor.handler({}, None)   # evento del programador (sin Records ni accion) → barrido
    assert r["espejo"] == {"publicado": True}
    assert worker.llamadas


def test_sonda_lee_salud_sin_escribir(worker):
    worker.respuesta = lambda: (200, {}, b'{"ok":true,"publicadoEn":null}')
    cloudflare.sondear()
    assert worker.llamadas[0][:2] == ("GET", f"{URL}/salud")
    assert estado.leer_tablero()["cloudflare-workers"]["estado"] == "OK"
