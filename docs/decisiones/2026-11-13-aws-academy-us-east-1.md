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
- Los recursos **sobreviven** al cierre de la sesión del lab, pero el presupuesto del lab es limitado: **elimina tus stages de prueba** (`serverless remove --stage dev-<alias>`) cuando no los uses.

## Verificación del lab (E0, 2026-11-14, issue #8)
Se probó con un stack de humo (`infra/verificacion/`) desplegado con `LabRole`. Las llamadas se hicieron **desde una Lambda**, porque `LabRole` tiene permisos distintos al usuario de la consola o la CLI (`voclabs`).

| Servicio | Resultado | Notas |
|---|---|---|
| Lambda `python3.12` | ✅ | Concurrencia de la cuenta: **1000**. Serverless v3 avisa "runtime no permitido" en el esquema, pero despliega bien: ignorar el warning |
| HTTP API (API Gateway v2) | ✅ | |
| **WebSocket API** | ✅ | Handshake `101 Switching Protocols` |
| DynamoDB + Streams + **PITR** + TTL | ✅ | El stream dispara la Lambda |
| SQS + DLQ → Lambda | ✅ | |
| Step Functions (`Wait`, `Map`, Lambda) con `LabRole` | ✅ | Plugin `serverless-step-functions` con `role:` |
| EventBridge **Scheduler** con `LabRole` | ✅ | |
| Regla de EventBridge → Step Functions con `LabRole` | ✅ | |
| SNS topic (publish) + suscripción de **email** | ✅ | El email requiere que el usuario **confirme** la suscripción. Funciona con `FilterPolicy` por usuario |
| Secrets Manager | ✅ | Crear vía CloudFormation y leer desde Lambda |
| SSM Parameter Store | ✅ | |
| S3 (versionado) + **static website** público | ✅ | Solo **HTTP** (sin HTTPS) |
| **CloudFront** | ❌ | Bloqueado por completo (ni `ListDistributions`, ni OAC, ni OAI) |
| **SES** | ❌ | `AccessDenied` desde la CLI y desde `LabRole` |
| **SNS SMS** | ❌ | `AuthorizationError` (sms-voice) |
| **Bedrock** | ❌ | `AccessDenied` |
| **Comprehend** | ❌ | `AccessDenied` |
| Nota de la CLI en Git Bash | ⚠️ | Exportar `MSYS_NO_PATHCONV=1` para rutas tipo `/aws/lambda/...` |

### Alternativas adoptadas
- **Frontend sin CloudFront**: S3 static website no da HTTPS, y el portal lo necesita para la **geolocalización** y la **voz** del navegador (requieren contexto seguro). Propuesta: servir el frontend por **HTTPS a través de API Gateway** (HTTP API → Lambda que entrega los archivos del bucket S3, con caché larga para los *assets*). El bucket sigue siendo el almacén, versionado. A confirmar en E1.
- **Notificaciones sin SES ni SMS**:
  1. **Email por SNS** (topic único + `FilterPolicy` por `usuarioId`; el usuario confirma una vez).
  2. **Notificaciones dentro de la app** (feed de seguimiento del portal; en vivo por WebSocket en E7).
  3. SMS/WhatsApp/Telegram vía la segunda nube o un bot (E8). Todo envío queda en el historial.
- **IA sin Bedrock ni Comprehend**: la IA **debe** venir de la segunda nube (refuerza D2).
