#!/usr/bin/env bash
# Al detenerse una sesión del AWS Academy Learner Lab, AWS desactiva las conexiones SQS → Lambda
# (event source mappings) de la cuenta: las métricas y los reportes quedan en cola sin procesarse.
# Este script las vuelve a activar. Ejecútalo después de cada "Start Lab" (scripts/deploy.sh también lo hace).
#   bash scripts/reactivar-lab.sh <stage>
set -euo pipefail
STAGE="${1:?Uso: bash scripts/reactivar-lab.sh <stage>}"
# Funciones con colas o streams (presupuesto de concurrencia D14: simulador+clasificador, segundo plano y motor).
for funcion in "telecorp-$STAGE-simulador" "telecorp-$STAGE-segundo-plano" "telecorp-$STAGE-detector"; do
  for uuid in $(aws lambda list-event-source-mappings --function-name "$funcion" \
      --query "EventSourceMappings[?State=='Disabled'].UUID" --output text 2>/dev/null); do
    aws lambda update-event-source-mapping --uuid "$uuid" --enabled >/dev/null
    echo "  ✔ reactivada la cola → $funcion"
  done
done
echo "✔ Conexiones de colas activas en $STAGE"

# Las Step Functions que estaban monitoreando un incidente fallan al apagarse el lab: reanudarlas.
# `POST /api/colectivos/reanudar` exige sesión de operador (Cognito). Este script ya trabaja con credenciales de AWS,
# así que invoca la Lambda directamente (solo un principal de IAM puede hacerlo; los visitantes HTTP no).
SALIDA=$(mktemp)
command -v cygpath >/dev/null 2>&1 && SALIDA=$(cygpath -m "$SALIDA")   # Git Bash en Windows: el AWS CLI necesita ruta de Windows
# Router único del API (D14): la ruta viaja en routeKey.
if aws lambda invoke --function-name "telecorp-$STAGE-api" --cli-binary-format raw-in-base64-out \
    --payload '{"routeKey":"POST /api/colectivos/reanudar","requestContext":{"authorizer":{"jwt":{"claims":{"sub":"sistema-reactivar-lab","cognito:groups":"[operadores]"}}}}}' \
    "$SALIDA" >/dev/null 2>&1; then
  echo "  Incidentes reanudados: $(cat "$SALIDA")"
else
  echo "  (no se pudo reanudar incidentes: ¿está desplegado telecorp-$STAGE-api?)"
fi
rm -f "$SALIDA"
