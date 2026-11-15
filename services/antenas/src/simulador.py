"""Simulador de antenas: genera la métrica de tráfico (GB/min) de cada antena del catálogo y la envía a SQS.

Lo invoca EventBridge Scheduler cada minuto (solo mientras el simulador está encendido) y emite
`muestrasPorMinuto` lecturas espaciadas para que el mapa se vea vivo.
Las fallas forzadas (SSM /telecorp/<stage>/simulador → fallas) reemplazan el valor generado.
"""
import hashlib
import json
import math
import os
import random
import time

import boto3

from telecorp import config, util, zonas

_sqs = boto3.client("sqs")


def _base_antena(antena_id: str) -> float:
    """Tráfico base estable por antena (75–110 GB/min), derivado de su id."""
    h = int(hashlib.sha256(antena_id.encode()).hexdigest()[:6], 16)
    return 75 + (h % 3500) / 100


def en_saturacion(antena_id: str, minuto_del_dia: float, prob_saturacion: float) -> bool:
    """Episodios de saturación de ~6 minutos (no lecturas sueltas): estable entre muestras del mismo bloque."""
    bloque = int(minuto_del_dia // 6)
    h = int(hashlib.sha256(f"{antena_id}:{bloque}".encode()).hexdigest()[:6], 16)
    return (h % 10000) < prob_saturacion * 10000


def generar_valor(antena_id: str, minuto_del_dia: float, prob_saturacion: float, rng=random) -> float:
    """Valor normal con ciclo diario suave y ruido; durante un episodio de saturación, >129."""
    if en_saturacion(antena_id, minuto_del_dia, prob_saturacion):
        return round(rng.uniform(132, 160), 1)
    ciclo = 12 * math.sin(2 * math.pi * (minuto_del_dia - 480) / 1440)  # pico a media tarde
    valor = _base_antena(antena_id) + ciclo + rng.gauss(0, 4)
    return round(min(max(valor, 62), 128), 1)


def metricas_actuales(fallas: dict, prob_saturacion: float) -> list:
    ahora = util.ahora()
    minuto = ahora.hour * 60 + ahora.minute
    medido_en = util.iso(ahora)
    salida = []
    for a in zonas.antenas():
        forzado = fallas.get(a["antenaId"])
        gb = float(forzado) if forzado is not None else generar_valor(a["antenaId"], minuto, prob_saturacion)
        lectura = {"antenaId": a["antenaId"], "zonaId": a["zonaId"], "medidoEn": medido_en, "gbPorMinuto": gb}
        if forzado is not None:
            lectura["simulada"] = True   # falla forzada por una persona o un escenario: nunca es un dato operativo
        salida.append(lectura)
    return salida


def enviar(metricas: list) -> None:
    url = os.environ["COLA_METRICAS_URL"]
    for i in range(0, len(metricas), 10):
        lote = metricas[i:i + 10]
        resp = _sqs.send_message_batch(
            QueueUrl=url,
            Entries=[{"Id": str(j), "MessageBody": json.dumps(m)} for j, m in enumerate(lote)],
        )
        if resp.get("Failed"):
            raise RuntimeError(f"SQS rechazó {len(resp['Failed'])} métricas: {resp['Failed'][:2]}")


def handler(event, context):
    """event = {} (Scheduler) o {"unaVez": true} (disparo inmediato desde el API)."""
    cfg = config.leer("simulador", usar_cache=False)
    muestras = 1 if event.get("unaVez") else max(1, int(cfg.get("muestrasPorMinuto", 4)))
    intervalo = 60 / muestras
    for n in range(muestras):
        inicio = time.time()
        if n > 0:
            cfg = config.leer("simulador", usar_cache=False)  # recoge fallas forzadas entre muestras
        enviar(metricas_actuales(cfg.get("fallas", {}), cfg.get("probSaturacion", 0.03)))
        # No dormir después de la última muestra ni pasarse del tiempo de la Lambda.
        if n < muestras - 1 and context.get_remaining_time_in_millis() > (intervalo + 5) * 1000:
            time.sleep(max(0, intervalo - (time.time() - inicio)))
    return {"muestras": muestras, "antenas": len(zonas.antenas())}
