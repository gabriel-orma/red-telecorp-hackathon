"""Historial inmutable: solo inserciones (contracts/schemas/evento-historial.schema.json)."""
import secrets

from telecorp import db, util


def registrar(entidad_id: str, entidad_tipo: str, tipo_evento: str, actor: str, detalle: str = "",
              estado_anterior=None, estado_nuevo=None, ocurrido_en: str | None = None) -> dict:
    ocurrido_en = ocurrido_en or util.ahora_iso()
    evento = {
        "entidadId": entidad_id,
        # Clave de orden única aunque coincidan el instante y el tipo.
        "sk": f"{ocurrido_en}#{tipo_evento}#{secrets.token_hex(3)}",
        "entidadTipo": entidad_tipo,
        "ocurridoEn": ocurrido_en,
        "tipoEvento": tipo_evento,
        "actor": actor,
        "detalle": detalle,
        "estadoAnterior": estado_anterior,
        "estadoNuevo": estado_nuevo,
    }
    db.tabla("historial").put_item(Item=evento, ConditionExpression="attribute_not_exists(sk)")
    return evento
