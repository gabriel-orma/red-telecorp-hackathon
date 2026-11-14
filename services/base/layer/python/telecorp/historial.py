"""Historial inmutable: solo inserciones (contracts/schemas/evento-historial.schema.json)."""
import secrets

from telecorp import db, util


def evento(entidad_id: str, entidad_tipo: str, tipo_evento: str, actor: str, detalle: str = "",
           estado_anterior=None, estado_nuevo=None, ocurrido_en: str | None = None, token: str | None = None) -> dict:
    """Construye el ítem del historial (sin escribirlo): sirve para incluirlo en una transacción.

    `token` fija la parte final de la clave de orden: con el mismo (`ocurrido_en`, `tipo_evento`, `token`) el evento es
    idempotente (un reintento no lo duplica). Sin `token`, es aleatorio y el evento siempre es nuevo.
    """
    ocurrido_en = ocurrido_en or util.ahora_iso()
    return {
        "entidadId": entidad_id,
        # Clave de orden única aunque coincidan el instante y el tipo.
        "sk": f"{ocurrido_en}#{tipo_evento}#{token or secrets.token_hex(3)}",
        "entidadTipo": entidad_tipo,
        "ocurridoEn": ocurrido_en,
        "tipoEvento": tipo_evento,
        "actor": actor,
        "detalle": detalle,
        "estadoAnterior": estado_anterior,
        "estadoNuevo": estado_nuevo,
    }


def registrar(entidad_id: str, entidad_tipo: str, tipo_evento: str, actor: str, detalle: str = "",
              estado_anterior=None, estado_nuevo=None, ocurrido_en: str | None = None, token: str | None = None) -> dict:
    item = evento(entidad_id, entidad_tipo, tipo_evento, actor, detalle, estado_anterior, estado_nuevo, ocurrido_en, token)
    db.tabla("historial").put_item(Item=item, ConditionExpression="attribute_not_exists(sk)")
    return item
