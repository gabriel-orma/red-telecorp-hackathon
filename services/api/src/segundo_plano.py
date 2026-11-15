"""Trabajo en segundo plano del API en UNA Lambda con concurrencia reservada (decisión D14):

- SQS `reportes`      → registrar el reporte (incidencias.registrar)
- DynamoDB Streams     → avisar a los paneles por WebSocket (tiempo_real.difundir)

Un lote de Lambda trae registros de una sola fuente, así que basta con mirar el primero.
"""
try:  # en Lambda el paquete es src/
    from src import incidencias, tiempo_real
except ModuleNotFoundError:  # pruebas locales
    import incidencias
    import tiempo_real


def handler(event, context):
    registros = event.get("Records") or []
    if not registros:
        return {"omitido": "sin registros"}
    if registros[0].get("eventSource") == "aws:sqs":
        return incidencias.registrar(event, context)
    # Avisos en vivo: si fallan, los paneles igual se ponen al día con su polling de respaldo.
    try:
        return tiempo_real.difundir(event, context)
    except Exception as e:  # noqa: BLE001
        print(f"difusor: aviso omitido ({e!r})")
        return {"omitido": "error al difundir"}
