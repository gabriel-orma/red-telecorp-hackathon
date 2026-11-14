"""Trigger PreSignUp de Cognito (decisión D9).

- Valida el perfil (DNI, zona del servicio, teléfono) contra las reglas y el catálogo.
- Auto-confirma la cuenta y el email: registro en un paso (decisión del equipo para la demo).
Lanzar una excepción rechaza el registro y Cognito devuelve el mensaje al cliente.
"""
import re

from telecorp import zonas


def handler(event, context):
    attrs = event["request"].get("userAttributes", {})
    dni = attrs.get("custom:dni", "")
    if not re.fullmatch(r"[0-9]{8,12}", dni):
        raise ValueError("El DNI/CE debe tener entre 8 y 12 dígitos")
    if not attrs.get("custom:numeroServicio"):
        raise ValueError("Falta el número del servicio")
    if not zonas.zona(attrs.get("custom:zonaId", "")):
        raise ValueError("Elige la zona de tu servicio")
    if attrs.get("phone_number") and not re.fullmatch(r"\+[0-9]{8,15}", attrs["phone_number"]):
        raise ValueError("El celular debe tener formato internacional, ej. +51999888777")

    event["response"]["autoConfirmUser"] = True
    event["response"]["autoVerifyEmail"] = True
    return event
