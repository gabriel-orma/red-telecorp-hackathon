#!/usr/bin/env bash
# Guarda la API key de Google Gemini (Google AI Studio) en AWS Secrets Manager (`telecorp/<stage>/ia`) y enciende Gemini.
# La clave se ve al pegarla (solo en tu terminal) y luego se muestra enmascarada; nunca se guarda en el repo ni en logs.
# Conserva los demás campos del secreto (límites, modelo, triageTexto…). Antes de guardar, comprueba la clave con una
# llamada gratuita que solo lista modelos (no genera texto).
#
#   bash scripts/gemini-secreto.sh <stage>
#
# Clave gratis, sin tarjeta: https://aistudio.google.com/apikey (con cualquier cuenta de Google).
set -euo pipefail
export MSYS_NO_PATHCONV=1
STAGE="${1:?uso: gemini-secreto.sh <stage>}"
NOMBRE="telecorp/${STAGE}/ia"
PY=""
for c in python3 python py; do "$c" -c "import json" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "ERROR: se necesita python"; exit 1; }

read -rp "Pega la API key de Gemini y presiona Enter: " CLAVE
CLAVE="$(printf '%s' "$CLAVE" | tr -d '[:space:]')"
[ -n "$CLAVE" ] || { echo "ERROR: clave vacía"; exit 1; }
echo "Recibida: ${CLAVE:0:4}…${CLAVE: -2} (${#CLAVE} caracteres). Comprobando con Google…"

PREVIO="$(aws secretsmanager get-secret-value --secret-id "$NOMBRE" --query SecretString --output text 2>/dev/null || true)"
TMP="$(mktemp)"; command -v cygpath >/dev/null 2>&1 && TMP="$(cygpath -m "$TMP")"
trap 'rm -f "$TMP"' EXIT; chmod 600 "$TMP" 2>/dev/null || true

CLAVE="$CLAVE" PREVIO="$PREVIO" "$PY" - > "$TMP" <<'PYEOF'
import json, os, sys, urllib.error, urllib.request
clave = os.environ["CLAVE"].strip()
req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1",
                             headers={"x-goog-api-key": clave, "User-Agent": "telecorp-config/1.0"})
try:
    urllib.request.urlopen(req, timeout=15).read()
except urllib.error.HTTPError as e:
    sys.stderr.write(f"ERROR: Google rechazó la clave (HTTP {e.code}). No se guardó nada.\n"); sys.exit(2)
try:
    previo = json.loads(os.environ.get("PREVIO") or "{}")
except ValueError:
    previo = {}
previo.pop("apiKey", None)            # marcador viejo "PENDIENTE-D2"
previo.update({"geminiApiKey": clave, "habilitada": True})
print(json.dumps(previo))
PYEOF

aws secretsmanager put-secret-value --secret-id "$NOMBRE" --secret-string "file://$TMP" >/dev/null
echo "✔ Clave válida y guardada en $NOMBRE (valor no mostrado). Gemini queda habilitado."
