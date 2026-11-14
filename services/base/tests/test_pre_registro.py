"""Pruebas del trigger PreSignUp de Cognito (D9)."""
import pytest

import pre_registro


def _evento(**attrs):
    base = {"custom:dni": "70123456", "custom:numeroServicio": "999111222", "custom:zonaId": "ZONA-02",
            "phone_number": "+51999111222"}
    return {"request": {"userAttributes": {**base, **attrs}}, "response": {}}


def test_perfil_valido_se_auto_confirma():
    r = pre_registro.handler(_evento(), None)["response"]
    assert r["autoConfirmUser"] and r["autoVerifyEmail"]


@pytest.mark.parametrize("attrs, mensaje", [
    ({"custom:dni": "7012345"}, "DNI"),
    ({"custom:zonaId": "ZONA-99"}, "zona"),
    ({"phone_number": "999111222"}, "celular"),
    ({"custom:numeroServicio": ""}, "servicio"),
])
def test_perfil_invalido_se_rechaza(attrs, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        pre_registro.handler(_evento(**attrs), None)
