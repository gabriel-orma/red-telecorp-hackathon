"""Una sola Lambda para el stack de antenas (presupuesto de concurrencia, decisión D14).

- EventBridge Scheduler (cada minuto) o {"unaVez": true} → simulador: encola las lecturas.
- SQS `metricas`                                       → clasificador: estado de cada antena.
Con concurrencia reservada 1, ambas tareas se turnan; la cola guarda las lecturas mientras tanto.
"""
try:  # en Lambda el paquete es src/
    from src import clasificador, simulador
except ModuleNotFoundError:  # pruebas locales
    import clasificador
    import simulador


def handler(event, context):
    if event.get("Records"):
        return clasificador.handler(event, context)
    return simulador.handler(event, context)
