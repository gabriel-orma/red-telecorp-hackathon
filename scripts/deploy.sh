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

URL="$(salida "telecorp-api-$STAGE" Url)"
if quiere frontend && [ -f frontend/package.json ]; then
  paso "Compilando frontend"
  (cd frontend && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build)
  BUCKET="$(salida "telecorp-api-$STAGE" BucketFrontendNombre)"
  paso "Publicando frontend en s3://$BUCKET"
  # assets con hash: caché larga; index.html y demás: sin caché
  aws s3 sync frontend/dist "s3://$BUCKET" --delete --only-show-errors
fi

printf '\n\033[1;32m✔ Listo.\033[0m  Centro de control: %s\n' "$URL"
