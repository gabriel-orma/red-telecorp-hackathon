"""Control de acceso del API (H01): identidad y rol de operador.

El autorizador JWT del HTTP API valida firma, emisor, audiencia y expiración del ID token de Cognito, pero NO sabe de
grupos. El rol se comprueba aquí, con el claim `cognito:groups` ya validado: una ruta de operador necesita las DOS capas
(autorizador en `serverless.yml` + `solo_operadores` en el handler). Si falta alguna, la ruta no se abre: sin
`requestContext.authorizer` el handler responde 401 (falla cerrado).

La identidad de una persona es el `sub` del token (inmutable, asignado por Cognito); `custom:dni` es un dato de perfil que
el usuario puede editar y NUNCA identifica a nadie.
"""
import functools
import re

from telecorp import http

GRUPO_OPERADORES = "operadores"
_SEPARADORES = re.compile(r"[\s,]+")
_ID_VALIDO = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,63}")


def claims_de(event: dict) -> dict:
    """Claims del ID token que el autorizador JWT dejó en el evento ({} si la ruta no pasó por un autorizador)."""
    ctx = (event or {}).get("requestContext") or {}
    jwt = (ctx.get("authorizer") or {}).get("jwt") or {}
    return jwt.get("claims") or {}


def grupos_de(claims: dict) -> set:
    """Grupos de Cognito. API Gateway entrega el arreglo como texto (`[operadores admin]`); se aceptan también listas
    y JSON (`["operadores"]`) para no depender del formato exacto."""
    bruto = (claims or {}).get("cognito:groups")
    if bruto is None:
        return set()
    if isinstance(bruto, (list, tuple, set)):
        elementos = [str(g) for g in bruto]
    else:
        elementos = _SEPARADORES.split(str(bruto).strip().strip("[]"))
    return {g for g in (e.strip().strip("\"'") for e in elementos) if g}


def identidad(event: dict):
    """`sub` del token o None. Es el `usuarioId` de los reportes y el `actor` de las acciones de operador."""
    sub = claims_de(event).get("sub")
    return sub if isinstance(sub, str) and sub else None


def id_valido(identificador) -> bool:
    """Un `sub` real de Cognito es un UUID; se acepta un conjunto seguro de caracteres (sin separadores de ruta ni
    de clave como `#`) para que nunca colisione con claves internas (`COLECTIVO#…`) ni rompa expresiones."""
    return isinstance(identificador, str) and _ID_VALIDO.fullmatch(identificador) is not None


def es_operador(event: dict) -> bool:
    sub = identidad(event)
    return id_valido(sub) and GRUPO_OPERADORES in grupos_de(claims_de(event))


def solo_operadores(manejador):
    """Decorador de handlers: 401 sin sesión validada, 403 si la sesión no es de un operador."""

    @functools.wraps(manejador)
    def protegido(event, context):
        if not id_valido(identidad(event)):
            return http.error(401, "Inicia sesión para continuar")
        if not es_operador(event):
            return http.error(403, "Esta acción es solo para operadores")
        return manejador(event, context)

    return protegido
