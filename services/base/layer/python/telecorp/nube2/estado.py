"""Estado compartido de las integraciones: cupos atómicos, disyuntor y tablero de salud (`GET /api/nubes`).

Todo vive en la tabla `dedup` (ya existente, con TTL `expiraEn`): no hay recursos nuevos ni costo fijo.

    LIMITE#<nombre>#<ventana>   contador atómico por ventana fija (cupos por minuto/hora/día)
    DISYUNTOR#<nombre>          fallos seguidos y hasta cuándo no se llama al servicio
    NUBE#<servicio>             tablero: estado, última llamada, latencia, contador de llamadas, último error

Nada aquí lanza excepciones al flujo del negocio: ante un fallo de DynamoDB, un cupo se considera NO concedido
(se prefiere no llamar a un servicio de pago o con cupo escaso antes que excederlo) y el tablero es mejor esfuerzo.
"""
import time

from botocore.exceptions import ClientError

from telecorp import db, util

TTL_TABLERO_DIAS = 30
SERVICIOS = ("azure-acs", "azure-maps", "gcp-bigquery", "gcp-gemini", "cloudflare-workers")


def _t():
    return db.tabla("dedup")


# ---------------------------------------------------------------- Cupos
def reservar_cupo(nombre: str, limite: int, segundos: int) -> bool:
    """Reserva UNA unidad de un cupo por ventana fija. True si cabe, False si se agotó (o si no se pudo comprobar)."""
    ventana = int(time.time()) // max(1, segundos)
    try:
        _t().update_item(
            Key={"clave": f"LIMITE#{nombre}#{ventana}"},
            UpdateExpression="ADD n :uno SET expiraEn = :exp",
            ConditionExpression="attribute_not_exists(n) OR n < :lim",
            ExpressionAttributeValues={":uno": 1, ":lim": int(limite), ":exp": (ventana + 2) * segundos})
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            print(f"nube2: no se pudo reservar cupo '{nombre}' ({e.response['Error']['Code']})")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"nube2: no se pudo reservar cupo '{nombre}' ({type(e).__name__})")
        return False


# ---------------------------------------------------------------- Disyuntor
def disyuntor_abierto(nombre: str) -> bool:
    try:
        it = _t().get_item(Key={"clave": f"DISYUNTOR#{nombre}"}).get("Item")
        return bool(it and int(it.get("abiertoHasta", 0)) > time.time())
    except Exception:  # noqa: BLE001 - sin información: se deja pasar (el timeout acota el daño)
        return False


def registrar_fallo(nombre: str, umbral: int = 3, pausa_s: int = 300) -> None:
    """Cuenta un fallo; al llegar al umbral abre el disyuntor `pausa_s` segundos y reinicia la cuenta."""
    try:
        ahora = int(time.time())
        r = _t().update_item(Key={"clave": f"DISYUNTOR#{nombre}"}, UpdateExpression="ADD fallos :uno SET expiraEn = :exp",
                             ExpressionAttributeValues={":uno": 1, ":exp": ahora + 86400}, ReturnValues="UPDATED_NEW")
        if int(r["Attributes"]["fallos"]) >= umbral:
            _t().update_item(Key={"clave": f"DISYUNTOR#{nombre}"}, UpdateExpression="SET abiertoHasta = :h, fallos = :cero",
                             ExpressionAttributeValues={":h": ahora + pausa_s, ":cero": 0})
    except Exception as e:  # noqa: BLE001
        print(f"nube2: disyuntor '{nombre}' no actualizado ({type(e).__name__})")


def registrar_exito(nombre: str) -> None:
    try:
        _t().update_item(Key={"clave": f"DISYUNTOR#{nombre}"}, UpdateExpression="SET fallos = :cero, expiraEn = :exp",
                         ExpressionAttributeValues={":cero": 0, ":exp": int(time.time()) + 86400})
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------- Tablero de salud
def anotar(servicio: str, ok: bool, latencia_ms: int | None = None, error: str | None = None, estado: str | None = None,
           cuenta: bool | None = None) -> None:
    """Mejor esfuerzo. `estado` explícito (p. ej. "NO_CONFIGURADA"); si no, OK/ERROR según `ok`.

    `contador` cuenta LLAMADAS REALES a la nube. Por eso una anotación con `estado` explícito (no se llamó a nadie) no suma, y quien
    anota por segunda vez una misma llamada (p. ej. la respuesta llegó pero era inválida) pasa `cuenta=False`."""
    suma = (estado is None) if cuenta is None else cuenta
    try:
        ahora = util.ahora_iso()
        sets = {"estado": estado or ("OK" if ok else "ERROR"), "ultimaLlamada": ahora,
                "expiraEn": int(time.time()) + TTL_TABLERO_DIAS * 86400}
        if latencia_ms is not None:
            sets["latenciaMs"] = int(latencia_ms)
        if ok:
            sets["ultimaOk"] = ahora
        if error:
            sets["ultimoError"] = str(error)[:120]
        nombres = {f"#{i}": k for i, k in enumerate(sets)}
        valores = {f":{i}": v for i, v in enumerate(sets.values())}
        expr = "SET " + ", ".join(f"#{i} = :{i}" for i in range(len(sets)))
        if ok and "ultimoError" not in sets:
            expr += " REMOVE ultimoError"
        if suma:
            expr += " ADD contador :uno"
            valores[":uno"] = 1
        _t().update_item(Key={"clave": f"NUBE#{servicio}"}, UpdateExpression=expr,
                         ExpressionAttributeNames=nombres, ExpressionAttributeValues=valores)
    except Exception as e:  # noqa: BLE001
        print(f"nube2: tablero '{servicio}' no actualizado ({type(e).__name__})")


def leer_tablero() -> dict:
    """{servicio: {estado, ultimaLlamada, contador, latenciaMs, ultimoError}}; servicios sin uso → SIN_USO."""
    try:
        items = {i["clave"]: i for i in db.obtener_varios("dedup", "clave", [f"NUBE#{s}" for s in SERVICIOS])}
    except Exception:  # noqa: BLE001
        items = {}
    salida = {}
    for s in SERVICIOS:
        it = items.get(f"NUBE#{s}")
        salida[s] = ({"estado": "SIN_USO", "ultimaLlamada": None, "contador": 0, "latenciaMs": None, "ultimoError": None}
                     if not it else {"estado": it.get("estado", "SIN_USO"), "ultimaLlamada": it.get("ultimaLlamada"),
                                     "contador": int(it.get("contador", 0)),
                                     "latenciaMs": int(it["latenciaMs"]) if "latenciaMs" in it else None,
                                     "ultimoError": it.get("ultimoError")})
    return salida
