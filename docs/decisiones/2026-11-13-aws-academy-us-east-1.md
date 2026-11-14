# D1 + D6: AWS Academy Learner Lab en us-east-1

- Estado: aceptada
- Issue: #1

## Contexto
Hay que definir con qué cuentas de AWS trabajamos y en qué región.

## Decisión
- Usamos **AWS Academy Learner Lab**: cada integrante tiene su propia cuenta de laboratorio.
- Región única: **`us-east-1`**.

## Consecuencias (léelas antes de diseñar o desplegar)
- **No se pueden crear roles IAM.** Todo recurso que necesite un rol (Lambda, Step Functions, EventBridge Scheduler, DynamoDB Streams → Lambda) usa el rol existente **`LabRole`**:
  ```yaml
  # serverless.yml
  provider:
    iam:
      role: arn:aws:iam::${aws:accountId}:role/LabRole
  ```
  Nada de `iamRoleStatements`, `iam.role.statements` ni plugins que creen roles.
- **Credenciales temporales**: caducan al terminar la sesión del lab (~4 h). Antes de desplegar, copia las nuevas desde *AWS Details* a `~/.aws/credentials` (incluye `aws_session_token`).
- **Cada integrante tiene su propia cuenta.** Los stages `dev-<alias>` viven en la cuenta de cada uno. El stage compartido **`demo`** se despliega en **una sola cuenta**, que se definirá en su momento y se documentará aquí.
- **Servicios posiblemente restringidos en Learner Lab. Verifica antes de construir encima** y documenta lo que encuentres en la bitácora:
  - **SES**: modo sandbox (solo a correos verificados) o bloqueado.
  - **SNS SMS**: probablemente no disponible. Alternativa: notificar por email o simular el SMS.
  - **Secrets Manager / SSM Parameter Store**: necesarios para la rúbrica. Confirmar cuál permite el lab.
  - **Concurrencia de Lambda** limitada en cuentas de laboratorio: tenerla en cuenta para la prueba de carga.
- Los recursos **sobreviven** al cierre de la sesión del lab, pero el presupuesto del lab es limitado: **elimina tus stages de prueba** (`serverless remove --stage dev-<alias>`) cuando no los uses.
