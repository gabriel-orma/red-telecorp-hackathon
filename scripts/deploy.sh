#!/usr/bin/env bash
# Despliega Red TeleCorp completo en la cuenta AWS de las credenciales actuales.
#   bash scripts/deploy.sh <stage> [componentes...]
#   componentes: base antenas api workflows frontend   (por defecto, todos y en ese orden)
# Ej.: bash scripts/deploy.sh dev-gabriel            → todo
#      bash scripts/deploy.sh dev-gabriel frontend   → solo recompila y publica el frontend
set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash en Windows: no convertir rutas tipo /aws/...

STAGE="${1:?Uso: bash scripts/deploy.sh <stage> [base antenas api workflows frontend]}"
shift || true
COMPONENTES="${*:-base antenas api workflows frontend}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"

paso() { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }
quiere() { [[ " $COMPONENTES " == *" $1 "* ]]; }
salida() { aws cloudformation describe-stacks --stack-name "$1" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text; }

paso "Verificando el presupuesto de concurrencia (D14: AWS Academy bloquea la cuenta con más de 10 Lambdas a la vez)"
PYT=python3; "$PYT" -c "import pytest, yaml" 2>/dev/null || PYT=python
if "$PYT" -c "import pytest, yaml" 2>/dev/null; then
  "$PYT" -m pytest -o addopts="" -p no:cacheprovider -q services/api/tests/test_presupuesto_concurrencia.py \
    || { echo "✗ El código supera el presupuesto de concurrencia. NO se despliega (ver docs/decisiones/2026-11-15-presupuesto-concurrencia.md)."; exit 1; }
else
  echo "✗ Falta pytest/pyyaml para verificar el presupuesto: pip install pytest pyyaml"; exit 1
fi

paso "Verificando credenciales AWS"
aws sts get-caller-identity --query Arn --output text || { echo "✗ Credenciales inválidas o expiradas (Learner Lab → AWS Details)"; exit 1; }

[ -d node_modules ] || { paso "Instalando Serverless Framework (npm ci)"; npm ci --no-audit --no-fund; }
SLS="$RAIZ/node_modules/.bin/serverless"

carpeta() { [ "$1" = workflows ] && echo "$RAIZ/workflows" || echo "$RAIZ/services/$1"; }
desplegar() {
  paso "Desplegando $1 (stage $STAGE)"
  (cd "$(carpeta "$1")" && "$SLS" deploy --stage "$STAGE" 2>&1 | grep -v "allowed values\|Invalid configuration\|Learn more about configuration\|^$")
}

if quiere base; then
  cp contracts/zonas.json services/base/layer/python/telecorp/zonas.json
  desplegar base
fi
quiere antenas && desplegar antenas
quiere api && desplegar api
quiere workflows && desplegar workflows

# El Learner Lab desactiva las conexiones SQS → Lambda al detenerse; un deploy sin cambios no las reactiva.
if quiere antenas || quiere api || quiere workflows; then
  paso "Verificando conexiones de colas (Learner Lab)"
  bash "$RAIZ/scripts/reactivar-lab.sh" "$STAGE"
fi

URL="$(salida "telecorp-api-$STAGE" Url)"
if quiere frontend && [ -f frontend/package.json ]; then
  paso "Compilando frontend"
  # Respaldo del estado público en Cloudflare (D15): la URL del Worker (no es secreta) sale del secreto de la integración.
  PY=python3; "$PY" -c "import json" 2>/dev/null || PY=python
  SECRETO_CF="$(aws secretsmanager get-secret-value --secret-id "telecorp/$STAGE/cloudflare" --query SecretString --output text 2>/dev/null || true)"
  ESPEJO="$(SECRETO_CF="$SECRETO_CF" "$PY" -c "import json,os; print(json.loads(os.environ['SECRETO_CF'] or '{}').get('url',''))" 2>/dev/null || true)"
  unset SECRETO_CF
  [ -n "$ESPEJO" ] && echo "Respaldo del estado público: $ESPEJO" || echo "Sin espejo de Cloudflare (opcional: bash scripts/cloudflare.sh $STAGE)"
  (cd frontend && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && VITE_ESPEJO_URL="$ESPEJO" npm run build)
  BUCKET="$(salida "telecorp-api-$STAGE" BucketFrontendNombre)"
  paso "Publicando frontend en s3://$BUCKET"
  # Sin Lambda (D14): el HTTP API entrega lo que guarda S3, así que el tipo, la caché y la compresión se fijan al subir.
  PY=python3; "$PY" -c "import boto3" 2>/dev/null || PY=python
  "$PY" scripts/publicar-frontend.py "$BUCKET"
fi

printf '\n\033[1;32m✔ Listo.\033[0m  Centro de control: %s\n' "$URL"
