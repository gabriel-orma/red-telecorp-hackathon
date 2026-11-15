#!/usr/bin/env bash
# Crea (o actualiza) una cuenta de OPERADOR en el User Pool del stage: usuario confirmado, contraseña permanente y
# grupo `operadores`. Para la demo y para probar el panel después de desplegar en una cuenta nueva.
#
#   bash scripts/crear-operador.sh <stage> <correo> [contraseña]
#
# Sin contraseña, genera una y la guarda en scripts/demo/.operador-<stage>.local (ignorado por git), sin imprimirla.
# Idempotente: si el usuario ya existe, solo fija la contraseña y lo agrega al grupo.
set -euo pipefail
export MSYS_NO_PATHCONV=1

STAGE="${1:?uso: crear-operador.sh <stage> <correo> [contraseña]}"
CORREO="${2:?falta el correo del operador}"
CLAVE="${3:-}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
ARCHIVO="$RAIZ/scripts/demo/.operador-$STAGE.local"

POOL="$(aws cloudformation describe-stacks --stack-name "telecorp-base-$STAGE" \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)"
[ -n "$POOL" ] && [ "$POOL" != "None" ] || { echo "✗ No encontré el User Pool de telecorp-base-$STAGE (¿desplegaste base?)"; exit 1; }

if [ -z "$CLAVE" ]; then
  # Cumple la política de Cognito: mayúscula, minúscula, número y símbolo.
  CLAVE="Op-$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 14)9a"
fi

# El trigger PreSignUp exige DNI, número de servicio y zona (los de un operador son de relleno).
if aws cognito-idp admin-get-user --user-pool-id "$POOL" --username "$CORREO" >/dev/null 2>&1; then
  echo "▶ El usuario ya existe: se actualiza"
else
  echo "▶ Creando usuario $CORREO"
  aws cognito-idp admin-create-user --user-pool-id "$POOL" --username "$CORREO" --message-action SUPPRESS \
    --user-attributes Name=email,Value="$CORREO" Name=email_verified,Value=true Name=name,Value="Operador NOC" \
      Name=custom:dni,Value=00000000 Name=custom:numeroServicio,Value=NOC Name=custom:zonaId,Value=ZONA-01 \
    >/dev/null
fi
aws cognito-idp admin-set-user-password --user-pool-id "$POOL" --username "$CORREO" --password "$CLAVE" --permanent
aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username "$CORREO" --group-name operadores

if [ -z "${3:-}" ]; then
  mkdir -p "$(dirname "$ARCHIVO")"
  printf 'correo=%s\nclave=%s\n' "$CORREO" "$CLAVE" >"$ARCHIVO"
  echo "✔ Operador listo. Credenciales en $ARCHIVO (no se suben al repo)."
else
  echo "✔ Operador listo."
fi
echo "  Ingresa en /portal/cuenta; si ya tenías sesión, ciérrala y vuelve a entrar para que el token traiga el grupo."
