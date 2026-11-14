"""Azure (ACS + Maps): PRUEBAS DE PROTOCOLO Y PARSEO, sin red ni nube.

Demuestran que la firma, el cuerpo y el parseo siguen la especificación; NO demuestran que Azure responda: eso se prueba
contra la nube real (ver lab/investigacion/fix-nube2-ia.md). El vector HMAC se calculó con OpenSSL (implementación
independiente de este código).
"""
import os

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("STAGE", "test")

import pytest  # noqa: E402

from telecorp.nube2 import azure_acs, azure_maps  # noqa: E402

CLAVE_B64 = "Y2xhdmUtZGUtcHJ1ZWJhLWFjcy0wMTIzNDU2Nzg5YWI="   # base64 de "clave-de-prueba-acs-0123456789ab"
HOST = "tccomm14917.unitedstates.communication.azure.com"
FECHA = "Sat, 14 Nov 2026 15:00:00 GMT"
RUTA = "/emails:send?api-version=2023-03-31"


# ---------------------------------------------------------------- ACS: firma HMAC
def test_firma_hmac_coincide_con_el_vector_calculado_con_openssl():
    cab = azure_acs.firmar("POST", RUTA, HOST, b'{"a":1}', CLAVE_B64, FECHA)
    assert cab["x-ms-content-sha256"] == "AVq9f1zFei3ZS3WQ8ErYCEJzkF7jPsXOvq5iJ2qX+GI="
    assert cab["x-ms-date"] == FECHA
    assert cab["Authorization"] == ("HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256"
                                    "&Signature=yh04cM97JZKvF5/Dk1wRolu189ve8s4wwX6TB82JsVo=")


def test_el_metodo_se_normaliza_a_mayusculas_y_el_cuerpo_vacio_tiene_su_hash():
    a = azure_acs.firmar("post", RUTA, HOST, b'{"a":1}', CLAVE_B64, FECHA)
    b = azure_acs.firmar("POST", RUTA, HOST, b'{"a":1}', CLAVE_B64, FECHA)
    assert a == b
    assert azure_acs.hash_contenido(b"") == "47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU="


def test_cambiar_cualquier_dato_firmado_cambia_la_firma():
    base = azure_acs.firmar("POST", RUTA, HOST, b"x", CLAVE_B64, FECHA)["Authorization"]
    assert azure_acs.firmar("POST", RUTA, HOST, b"y", CLAVE_B64, FECHA)["Authorization"] != base
    assert azure_acs.firmar("POST", RUTA + "&z=1", HOST, b"x", CLAVE_B64, FECHA)["Authorization"] != base
    assert azure_acs.firmar("POST", RUTA, "otro." + HOST, b"x", CLAVE_B64, FECHA)["Authorization"] != base
    assert azure_acs.firmar("POST", RUTA, HOST, b"x", CLAVE_B64, "Sat, 14 Nov 2026 15:00:01 GMT")["Authorization"] != base


def test_fecha_http_usa_el_formato_rfc1123_gmt():
    from datetime import datetime, timezone
    assert azure_acs.fecha_http(datetime(2026, 11, 14, 15, 0, 0, tzinfo=timezone.utc)) == FECHA


@pytest.mark.parametrize("endpoint, host", [
    (HOST, HOST), (f"https://{HOST}", HOST), (f"https://{HOST}/", HOST), (f"  http://{HOST}  ", HOST)])
def test_host_de_acepta_el_endpoint_con_o_sin_esquema(endpoint, host):
    assert azure_acs.host_de(endpoint) == host


def test_cuerpo_del_correo_sigue_el_esquema_de_la_api():
    c = azure_acs.cuerpo_correo("DoNotReply@d.azurecomm.net", "ana@correo.pe", "Asunto " * 60, "texto", "<p>hola</p>")
    assert c["senderAddress"] == "DoNotReply@d.azurecomm.net"
    assert c["recipients"] == {"to": [{"address": "ana@correo.pe"}]}
    assert len(c["content"]["subject"]) <= 200 and c["content"]["plainText"] == "texto" and c["content"]["html"] == "<p>hola</p>"
    assert c["userEngagementTrackingDisabled"] is True
    assert "html" not in azure_acs.cuerpo_correo("a@b.co", "x@y.pe", "s", "t")["content"]


@pytest.mark.parametrize("email, valido", [
    ("ana@correo.pe", True), ("ana.perez+aviso@utec.edu.pe", True),
    ("sim.70123456@example.com", False),          # los reportes simulados usan example.com
    ("a@example.org", False), ("a@localhost", False), ("a@red.test", False), ("a@mail.invalid", False),
    ("a@host.local", False), ("a@algo.demo", False),
    ("sin-arroba", False), ("a@b", False), ("", False), (None, False), ("a b@c.pe", False)])
def test_destinatario_valido_bloquea_formatos_malos_y_dominios_reservados(email, valido):
    assert azure_acs.destinatario_valido(email) is valido


# ---------------------------------------------------------------- Maps: parseo de respuestas REALES (forma verificada)
CLIMA_REAL = {"results": [{"phrase": "Mostly sunny", "temperature": {"value": 27.8, "unit": "C"}, "hasPrecipitation": False,
                           "wind": {"direction": {"degrees": 190}, "speed": {"value": 16.7, "unit": "km/h"}}}]}
GEO_REAL = {"features": [{"properties": {"address": {"formattedAddress": "Alfonso Ugarte Avenue, Lima, Province of Lima, Peru"}}}]}


def test_parsear_clima_con_la_forma_real_de_azure_maps():
    assert azure_maps.parsear_clima(CLIMA_REAL) == {"fuente": "AzureMaps", "frase": "Mostly sunny", "temperaturaC": 27.8,
                                                    "precipitacion": False, "vientoKmH": 16.7}


@pytest.mark.parametrize("malo", [None, {}, {"results": []}, {"results": [{}]}, {"results": [{"temperature": {"value": "x"}}]}, "texto"])
def test_parsear_clima_ante_respuestas_inesperadas_devuelve_none(malo):
    assert azure_maps.parsear_clima(malo) is None


def test_parsear_direccion_y_alertas():
    assert azure_maps.parsear_direccion(GEO_REAL) == {"fuente": "AzureMaps", "direccion": "Alfonso Ugarte Avenue, Lima, Province of Lima, Peru"}
    assert azure_maps.parsear_direccion({"features": []}) is None
    assert azure_maps.parsear_alertas({"results": []}) == []                    # sin alertas ≠ error
    a = azure_maps.parsear_alertas({"results": [{"description": {"localized": "Lluvia intensa"}, "category": "Rain", "priority": 2}]})
    assert a == [{"descripcion": "Lluvia intensa", "categoria": "Rain", "prioridad": 2, "fuente": "AzureMaps"}]
    assert azure_maps.parsear_alertas(None) is None
