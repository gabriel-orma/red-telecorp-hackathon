# E0: Verificación de servicios del Learner Lab

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 00:50
- **Issue / PR**: #8
- **Rama**: feat/8-verificacion-lab

## Qué se hizo
- Stack de humo `infra/verificacion` (Serverless v3 + `serverless-step-functions`), desplegado y **eliminado** después.
- `package.json` en la raíz con `serverless@3.40.0` y `serverless-step-functions@3.31.2` fijados (`npm install` y luego `npx serverless ...`).
- Resultados y alternativas documentados en D1.

## Resultado
- ✅ Lambda py3.12, HTTP API, WebSocket, DynamoDB (Streams/PITR/TTL), SQS+DLQ, Step Functions (Map/Wait), Scheduler, EventBridge → SFN, SNS topic + email, Secrets Manager, SSM, S3 website.
- ❌ **CloudFront, SES, SNS SMS, Bedrock, Comprehend.**

## Cómo probarlo
Ver `infra/verificacion/README.md`.

## Decisiones tomadas
- Frontend por HTTPS vía API Gateway + Lambda sobre S3 (CloudFront bloqueado). Actualizado en D5.
- Notificaciones: email por SNS con FilterPolicy + feed en la app. La IA debe venir de la 2.ª nube.

## Pendiente / siguiente paso
- Aprobación del equipo y luego E1.
- D2 (segunda nube): ahora es imprescindible también para la IA.

## Notas para los otros agentes
- Las llamadas desde la CLI usan el rol `voclabs`, **distinto** a `LabRole`: prueba los permisos desde una Lambda.
- En Git Bash: `export MSYS_NO_PATHCONV=1` antes de usar rutas `/aws/...` en la CLI.
- Ignora el warning de Serverless v3 sobre `python3.12`.
