#!/usr/bin/env bash
# Elimina todos los stacks de un stage (orden inverso) para no gastar presupuesto del lab.
#   bash scripts/remove.sh <stage>
# Vacía antes los buckets versionados: CloudFormation no puede borrar un bucket con objetos.
set -euo pipefail
export MSYS_NO_PATHCONV=1

STAGE="${1:?Uso: bash scripts/remove.sh <stage>}"
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
SLS="$RAIZ/node_modules/.bin/serverless"

vaciar_bucket() {
  local b="$1"
  [ -z "$b" ] || [ "$b" = "None" ] && return 0
  echo "  Vaciando s3://$b (todas las versiones)"
  python - "$b" <<'EOF'
import json, subprocess, sys
b = sys.argv[1]
while True:
    out = subprocess.run(["aws", "s3api", "list-object-versions", "--bucket", b, "--max-items", "1000", "--output", "json"],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out or "{}")
    objs = [{"Key": o["Key"], "VersionId": o["VersionId"]} for o in d.get("Versions", []) + d.get("DeleteMarkers", [])]
    if not objs:
        break
    subprocess.run(["aws", "s3api", "delete-objects", "--bucket", b, "--delete", json.dumps({"Objects": objs, "Quiet": True})],
                   check=True, capture_output=True)
EOF
}

for servicio in workflows api antenas base; do
  pila="telecorp-$servicio-$STAGE"
  if ! aws cloudformation describe-stacks --stack-name "$pila" >/dev/null 2>&1; then
    echo "· $pila no existe, se omite"; continue
  fi
  echo "▶ Eliminando $pila"
  for recurso in $(aws cloudformation list-stack-resources --stack-name "$pila" \
      --query "StackResourceSummaries[?ResourceType=='AWS::S3::Bucket'].PhysicalResourceId" --output text); do
    vaciar_bucket "$recurso"
  done
  dir="$RAIZ/services/$servicio"; [ "$servicio" = workflows ] && dir="$RAIZ/workflows"
  (cd "$dir" && "$SLS" remove --stage "$STAGE" 2>&1 | grep -v "allowed values\|Invalid configuration\|Learn more about configuration\|^$")
done
echo "✔ Stage $STAGE eliminado"
