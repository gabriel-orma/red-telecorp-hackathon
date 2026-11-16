"""Motor único del stack workflows (presupuesto de concurrencia, decisión D14).

Antes: detector + reconciliador + 17 Lambdas de pasos de Step Functions = 19 funciones que podían correr a la vez.
Ahora UNA función con concurrencia reservada 2 atiende:
- DynamoDB Streams (incidencias, antenas)        → detector.handler
- EventBridge cada 5 min                          → detector.reconciliar
- Tareas de Step Functions {"accion": ..., ...}   → el paso pedido (PASOS)
Si el motor está ocupado, Step Functions reintenta el paso (Retry de Lambda.TooManyRequestsException) y los streams esperan.
"""
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(__file__))  # imports hermanos (el handler se carga como src/motor)

import detector  # noqa: E402
import escenario  # noqa: E402
import pasos  # noqa: E402
import recurrencia  # noqa: E402

# accion (la que pone cada Task en statemachines/*.yml) → función
PASOS = {
    "prepararNotificacion": pasos.preparar_notificacion,
    "notificarLote": pasos.notificar_lote,
    "verificarInfraestructura": pasos.verificar_infraestructura,
    "priorizar": pasos.priorizar,
    "resumir": pasos.resumir,
    "confirmar": pasos.confirmar,
    "reverificar": pasos.reverificar,
    "restablecer": pasos.restablecer,
    "cerrar": pasos.cerrar,
    "sinResolver": pasos.sin_resolver,
    "manejarFallo": pasos.manejar_fallo,
    "escenarioPreparar": escenario.preparar,
    "escenarioOleada": escenario.aplicar_oleada,
    "escenarioFinalizar": escenario.finalizar,
    "recurrenciaContar": recurrencia.contar,
    "recurrenciaMarcar": recurrencia.marcar,
    "recurrenciaResumen": recurrencia.resumen,
}


def handler(event, context):
    if isinstance(event, dict) and "accion" in event:
        accion = event["accion"]
        if accion not in PASOS:
            raise ValueError(f"Paso desconocido: {accion}")
        # Tasks sin Parameters propios envían {"accion", "datos": <entrada completa>}; el resto, sus campos directos.
        entrada = event["datos"] if "datos" in event else {k: v for k, v in event.items() if k != "accion"}
        return PASOS[accion](entrada, context)
    if isinstance(event, dict) and event.get("Records"):
        return detector.handler(event, context)
    return detector.reconciliar(event, context)   # programación cada 5 min (EventBridge)
