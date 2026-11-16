#!/usr/bin/env bash
# Tercera nube (D15): despliega el espejo del estado público en Cloudflare Workers + KV y entrega su URL y token a AWS.
#   bash scripts/cloudflare.sh <stage>
# Requisitos: cuenta gratuita de Cloudflare y haber iniciado sesión UNA vez con:  npx wrangler@4.154.0 login
# Idempotente: reutiliza el KV, el token (si ya existe en AWS) y actualiza el Worker. No imprime el token.
# No crea Lambdas (D14): AWS publica desde el barrido que el motor `detector` ya hace cada 5 minutos.
set -euo pipefail
export MSYS_NO_PATHCONV=1

STAGE="${1:?uso: bash scripts/cloudflare.sh <stage>}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$RAIZ/edge/estado"
CONFIG="wrangler.$STAGE.toml"
WRANGLER=(npx --yes wrangler@4.154.0)
NOMBRE_SECRETO="telecorp/$STAGE/cloudflare"
KV_TITULO="telecorp-$STAGE-estado"
PY=python3; "$PY" -c "import json" 2>/dev/null || PY=python

paso() { printf '\n\033[1;35m▶ %s\033[0m\n' "$*"; }
cd "$DIR"

paso "Pruebas del Worker"
node --test test/worker.test.mjs >/dev/null || { echo "✗ Fallan las pruebas del Worker (node --test edge/estado/test/worker.test.mjs)"; exit 1; }
echo "ok"

paso "Sesión de Cloudflare"
"${WRANGLER[@]}" whoami 2>&1 | grep -qi "logged in" || { echo "✗ No hay sesión. Ejecuta primero: npx wrangler@4.154.0 login"; exit 1; }
echo "ok"

paso "KV $KV_TITULO"
buscar_kv() { "${WRANGLER[@]}" kv namespace list 2>/dev/null | "$PY" -c "
import json, sys
texto = sys.stdin.read(); texto = texto[texto.find('['):]
print(next((n['id'] for n in json.loads(texto or '[]') if n['title'] == sys.argv[1]), ''))" "$KV_TITULO"; }
KV_ID="$(buscar_kv)"
if [ -z "$KV_ID" ]; then
  "${WRANGLER[@]}" kv namespace create "$KV_TITULO" >/dev/null
  KV_ID="$(buscar_kv)"
fi
[ -n "$KV_ID" ] || { echo "✗ No se pudo crear o encontrar el KV $KV_TITULO"; exit 1; }
echo "id $KV_ID"
sed -e "s/__STAGE__/$STAGE/" -e "s/__KV_ID__/$KV_ID/" wrangler.plantilla.toml > "$CONFIG"

paso "Desplegando el Worker telecorp-estado-$STAGE"
SALIDA="$("${WRANGLER[@]}" deploy --config "$CONFIG" 2>&1)" || { echo "$SALIDA" | tail -20; exit 1; }
URL="$(echo "$SALIDA" | grep -oE 'https://[a-zA-Z0-9.-]+\.workers\.dev' | head -1)"
[ -n "$URL" ] || { echo "$SALIDA" | tail -20; echo "✗ No se encontró la URL workers.dev (¿falta registrar el subdominio workers.dev en el panel de Cloudflare?)"; exit 1; }
echo "$URL"

paso "Token de publicación"
PREVIO="$(aws secretsmanager get-secret-value --secret-id "$NOMBRE_SECRETO" --query SecretString --output text 2>/dev/null || true)"
TOKEN="$(PREVIO="$PREVIO" "$PY" -c "
import json, os, secrets
try: t = json.loads(os.environ['PREVIO'] or '{}').get('token')
except ValueError: t = None
print(t or secrets.token_urlsafe(32))")"
printf '%s' "$TOKEN" | "${WRANGLER[@]}" secret put TOKEN_PUBLICACION --config "$CONFIG" >/dev/null
echo "cargado en el Worker (valor no mostrado)"

paso "Secreto $NOMBRE_SECRETO en AWS Secrets Manager"
TMP="$(mktemp)"; command -v cygpath >/dev/null 2>&1 && TMP="$(cygpath -m "$TMP")"
trap 'rm -f "$TMP"' EXIT; chmod 600 "$TMP" 2>/dev/null || true
URL="$URL" TOKEN="$TOKEN" "$PY" -c "import json, os; print(json.dumps({'url': os.environ['URL'], 'token': os.environ['TOKEN']}))" > "$TMP"
if aws secretsmanager describe-secret --secret-id "$NOMBRE_SECRETO" >/dev/null 2>&1; then
  aws secretsmanager put-secret-value --secret-id "$NOMBRE_SECRETO" --secret-string "file://$TMP" >/dev/null
else
  aws secretsmanager create-secret --name "$NOMBRE_SECRETO" --description "Espejo del estado en Cloudflare (D15) - Red TeleCorp $STAGE" \
      --tags Key=proyecto,Value=red-telecorp --secret-string "file://$TMP" >/dev/null
fi
echo "guardado (valores no mostrados)"

printf '\n\033[1;32m✔ Cloudflare listo.\033[0m Página de estado: %s\n' "$URL"
echo "AWS publicará el estado en el próximo barrido (≤ 5 min). Para que la página pública use el respaldo,"
echo "recompila el frontend:  bash scripts/deploy.sh $STAGE frontend"
