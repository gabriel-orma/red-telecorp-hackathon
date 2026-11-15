"""Router único del API (presupuesto de concurrencia, decisión D14).

AWS Academy Learner Lab permite como máximo 10 ejecuciones de Lambda a la vez en TODA la cuenta; superarlo desactiva la
cuenta. Antes había una Lambda por ruta (32): una pantalla que pedía 5 datos usaba 5 Lambdas en paralelo. Ahora todas las
rutas HTTP y WebSocket llegan a ESTA función, que tiene concurrencia reservada (tope duro de AWS): si llegan más pedidos
que el tope, API Gateway responde "ocupado" y el frontend reintenta.

Los handlers no cambian: este módulo solo elige cuál llamar según `routeKey` (HTTP API v2 y WebSocket lo traen).
"""
import importlib

# routeKey → (módulo en src/, función). El autorizador de cada ruta sigue en serverless.yml (prueba: test_router.py).
RUTAS = {
    "GET /api/antenas": ("antenas", "listar_antenas"),
    "GET /api/zonas": ("antenas", "listar_zonas"),
    "GET /api/zonas/ubicar": ("antenas", "ubicar_zona"),
    "GET /api/antenas/{antenaId}/metricas": ("antenas", "metricas_antena"),
    "GET /api/simulador": ("simulador", "obtener"),
    "PUT /api/simulador": ("simulador", "actualizar"),
    "POST /api/reportes": ("incidencias", "crear_reporte"),
    "GET /api/mis-reportes": ("incidencias", "mis_reportes"),
    "GET /api/estado": ("estado", "estado"),
    "GET /api/config": ("estado", "config"),
    "GET /api/incidencias": ("incidencias", "listar"),
    "GET /api/incidencias/{incidenciaId}": ("incidencias", "obtener"),
    "GET /api/operador/incidencias": ("incidencias", "listar_operador"),
    "GET /api/operador/incidencias/{incidenciaId}": ("incidencias", "obtener_operador"),
    "PATCH /api/incidencias/{incidenciaId}/estado": ("incidencias", "cambiar_estado"),
    "GET /api/colectivos": ("colectivos", "listar"),
    "GET /api/colectivos/{colectivoId}": ("colectivos", "obtener"),
    "POST /api/colectivos/reanudar": ("colectivos", "reanudar"),
    "POST /api/colectivos/{colectivoId}/restablecer": ("colectivos", "restablecer"),
    "GET /api/analitica": ("analitica", "analitica"),
    "POST /api/recurrencia": ("analitica", "ejecutar_recurrencia"),
    "GET /api/nubes": ("nubes", "obtener"),
    "GET /api/linea-tiempo": ("linea_tiempo", "linea_tiempo"),
    "GET /api/escenarios": ("escenarios", "obtener"),
    "POST /api/escenarios": ("escenarios", "lanzar"),
    "POST /api/escenarios/reiniciar": ("escenarios", "reiniciar"),
    # WebSocket (tiempo real)
    "$connect": ("tiempo_real", "conectar"),
    "$disconnect": ("tiempo_real", "desconectar"),
    "$default": ("tiempo_real", "mensaje"),
}

# Rutas que exigen el autorizador JWT de Cognito en serverless.yml (además de la comprobación de grupo del handler).
CON_AUTORIZADOR = {
    "PUT /api/simulador", "GET /api/simulador", "POST /api/reportes", "GET /api/mis-reportes",
    "GET /api/operador/incidencias", "GET /api/operador/incidencias/{incidenciaId}",
    "PATCH /api/incidencias/{incidenciaId}/estado", "GET /api/colectivos/{colectivoId}",
    "POST /api/colectivos/reanudar", "POST /api/colectivos/{colectivoId}/restablecer", "POST /api/recurrencia",
    "GET /api/nubes", "GET /api/linea-tiempo", "POST /api/escenarios", "POST /api/escenarios/reiniciar",
}

_modulos: dict = {}


def _modulo(nombre: str):
    if nombre not in _modulos:
        try:  # en Lambda el paquete es src/
            _modulos[nombre] = importlib.import_module(f"src.{nombre}")
        except ModuleNotFoundError:  # pruebas locales (pytest añade services/api/src al path)
            _modulos[nombre] = importlib.import_module(nombre)
    return _modulos[nombre]


def clave_ruta(event: dict) -> str | None:
    """routeKey del evento: HTTP API v2 lo trae arriba; WebSocket, en requestContext."""
    return event.get("routeKey") or (event.get("requestContext") or {}).get("routeKey")


def handler(event, context):
    clave = clave_ruta(event)
    destino = RUTAS.get(clave or "")
    if not destino:
        return {"statusCode": 404, "headers": {"content-type": "application/json"}, "body": '{"error": "Ruta no encontrada"}'}
    modulo, funcion = destino
    return getattr(_modulo(modulo), funcion)(event, context)
