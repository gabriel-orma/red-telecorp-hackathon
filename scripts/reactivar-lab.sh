#!/usr/bin/env bash
# Al detenerse una sesión del AWS Academy Learner Lab, AWS desactiva las conexiones SQS → Lambda
# (event source mappings) de la cuenta: las métricas y los reportes quedan en cola sin procesarse.
# Este script las vuelve a activar. Ejecútalo después de cada "Start Lab" (scripts/deploy.sh también lo hace).
#   bash scripts/reactivar-lab.sh <stage>
set -euo pipefail
STAGE="${1:?Uso: bash scripts/reactivar-lab.sh <stage>}"
for funcion in "telecorp-$STAGE-clasificador" "telecorp-api-$STAGE-registrarReporte" "telecorp-$STAGE-detector" "telecorp-api-$STAGE-difusor"; do
  for uuid in $(aws lambda list-event-source-mappings --function-name "$funcion" \
      --query "EventSourceMappings[?State=='Disabled'].UUID" --output text 2>/dev/null); do
    aws lambda update-event-source-mapping --uuid "$uuid" --enabled >/dev/null
    echo "  ✔ reactivada la cola → $funcion"
  done
done
echo "✔ Conexiones de colas activas en $STAGE"

# Las Step Functions que estaban monitoreando un incidente fallan al apagarse el lab: reanudarlas.
URL=$(aws cloudformation describe-stacks --stack-name "telecorp-api-$STAGE" --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text 2>/dev/null || true)
if [ -n "$URL" ] && [ "$URL" != "None" ]; then
  echo "  Incidentes reanudados: $(curl -s -X POST "$URL/api/colectivos/reanudar")"
fi
