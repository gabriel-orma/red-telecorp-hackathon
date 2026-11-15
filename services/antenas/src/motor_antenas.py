"""Una sola Lambda para el stack de antenas (presupuesto de concurrencia, decisión D14).

- EventBridge Scheduler (cada minuto) o {"unaVez": true} → simulador: encola las lecturas.
- SQS `metricas`                                       → clasificador: estado de cada antena.
Con concurrencia reservada 1, ambas tareas se turnan; la cola guarda las lecturas mientras tanto.

Lecturas programadas: el simulador encola las 4 muestras del minuto de una vez (con retraso de SQS). Si mientras tanto
un escenario o un operador fuerza o quita una falla, la muestra programada traería el valor viejo y "repararía" o
"rompería" la antena por error. Por eso, al procesarla, se aplican las fallas forzadas VIGENTES (`vigentes`).
"""
import json

try:  # en Lambda el paquete es src/
    from src import clasificador, simulador
except ModuleNotFoundError:  # pruebas locales
    import clasificador
    import simulador

from telecorp import config, util


def vigentes(lectura: dict, fallas: dict, prob_saturacion: float) -> dict:
    """La lectura con las fallas forzadas de AHORA (solo lecturas del simulador; un medidor real no se toca)."""
    if not lectura.get("programada"):
        return lectura
    forzado = fallas.get(lectura["antenaId"])
    if forzado is not None:
        return {**lectura, "gbPorMinuto": float(forzado), "simulada": True}
    if lectura.get("simulada"):   # estaba forzada al programarse y ya no lo está: vuelve a su tráfico normal
        momento = util.parse_iso(lectura["medidoEn"])
        valor = simulador.generar_valor(lectura["antenaId"], momento.hour * 60 + momento.minute, prob_saturacion)
        return {k: v for k, v in lectura.items() if k != "simulada"} | {"gbPorMinuto": valor}
    return lectura


def handler(event, context):
    if event.get("Records"):
        cfg = config.leer("simulador", usar_cache=False)   # una lectura de SSM por lote
        fallas, prob = cfg.get("fallas", {}), cfg.get("probSaturacion", 0.03)
        for r in event["Records"]:
            r["body"] = json.dumps(vigentes(json.loads(r["body"]), fallas, prob))
        return clasificador.handler(event, context)
    return simulador.handler(event, context)
