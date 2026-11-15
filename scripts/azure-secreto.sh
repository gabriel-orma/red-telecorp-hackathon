#!/usr/bin/env bash
# Copia las claves de Azure (Communication Services + Maps) a AWS Secrets Manager (`telecorp/<stage>/azure`).
# NO imprime ningún valor secreto. Idempotente: si el secreto ya existe lo actualiza y CONSERVA su lista `destinatarios`.
#
#   bash scripts/azure-secreto.sh <stage> <grupo> <servicio-comunicacion> <servicio-correo> <cuenta-maps> [destinatarios]
#   destinatarios: correos exactos o dominios separados por comas, p. ej. "ana@correo.pe,@miempresa.com".
#                  Sin lista, el sistema NO envía correo por Azure (ver docs/despliegue-azure.md).
#
# Requisitos: `az` con sesión iniciada en la suscripción, `aws` con credenciales del Learner Lab y `python3` o `python`.
set -euo pipefail
export MSYS_NO_PATHCONV=1

STAGE="${1:?uso: azure-secreto.sh <stage> <grupo> <servicio-comunicacion> <servicio-correo> <cuenta-maps> [destinatarios]}"
RG="${2:?falta el grupo de recursos}"; ACS="${3:?falta el servicio de Communication Services}"
CORREO="${4:?falta el servicio de correo (Email Communication Service)}"; MAPS="${5:?falta la cuenta de Azure Maps}"
DESTINATARIOS="${6:-}"
PY=""   # el primer intérprete que FUNCIONE (en Windows `python3` suele ser un atajo roto de la Tienda)
for candidato in python3 python py; do
  if "$candidato" -c "import json" >/dev/null 2>&1; then PY="$candidato"; break; fi
done
[ -n "$PY" ] || { echo "ERROR: se necesita python3 o python"; exit 1; }
NOMBRE="telecorp/${STAGE}/azure"

HOST="$(az communication show -n "$ACS" -g "$RG" --query hostName -o tsv)"
CLAVE_ACS="$(az communication list-key -n "$ACS" -g "$RG" --query primaryKey -o tsv)"
DOMINIO="$(az communication email domain show --domain-name AzureManagedDomain --email-service-name "$CORREO" -g "$RG" --query mailFromSenderDomain -o tsv)"
CLAVE_MAPS="$(az maps account keys list -n "$MAPS" -g "$RG" --query primaryKey -o tsv)"
for v in HOST CLAVE_ACS DOMINIO CLAVE_MAPS; do [ -n "${!v}" ] || { echo "ERROR: Azure no devolvió $v"; exit 1; }; done

# Valor previo del secreto (si existe), solo para conservar `destinatarios`; nunca se muestra.
PREVIO="$(aws secretsmanager get-secret-value --secret-id "$NOMBRE" --query SecretString --output text 2>/dev/null || true)"

TMP="$(mktemp)"; command -v cygpath >/dev/null 2>&1 && TMP="$(cygpath -m "$TMP")"   # Git Bash: el AWS CLI necesita ruta de Windows
trap 'rm -f "$TMP"' EXIT; chmod 600 "$TMP" 2>/dev/null || true
HOST="$HOST" CLAVE_ACS="$CLAVE_ACS" DOMINIO="$DOMINIO" CLAVE_MAPS="$CLAVE_MAPS" DESTINATARIOS="$DESTINATARIOS" PREVIO="$PREVIO" \
"$PY" - > "$TMP" <<'PYEOF'
import json, os
previo = {}
try:
    previo = json.loads(os.environ.get("PREVIO") or "{}")
except ValueError:
    pass
lista = [x.strip() for x in os.environ.get("DESTINATARIOS", "").split(",") if x.strip()] or previo.get("destinatarios", [])
print(json.dumps({"acsEndpoint": os.environ["HOST"], "acsKey": os.environ["CLAVE_ACS"], "acsSender": "DoNotReply@" + os.environ["DOMINIO"],
                  "mapsKey": os.environ["CLAVE_MAPS"], "destinatarios": lista}))
PYEOF

if aws secretsmanager describe-secret --secret-id "$NOMBRE" >/dev/null 2>&1; then
  aws secretsmanager put-secret-value --secret-id "$NOMBRE" --secret-string "file://$TMP" --query VersionId --output text >/dev/null
  echo "secreto actualizado: $NOMBRE"
else
  aws secretsmanager create-secret --name "$NOMBRE" --description "Credenciales Azure (ACS correo + Maps) - Red TeleCorp $STAGE" \
      --tags Key=proyecto,Value=red-telecorp --secret-string "file://$TMP" --query Name --output text >/dev/null
  echo "secreto creado: $NOMBRE"
fi
N="$("$PY" -c "import json,sys; print(len(json.load(open(sys.argv[1])).get('destinatarios', [])))" "$TMP")"
echo "claves guardadas (valores no mostrados). Destinatarios autorizados: $N"
[ "$N" -gt 0 ] || echo "AVISO: sin destinatarios autorizados el sistema no enviará correo por Azure."
