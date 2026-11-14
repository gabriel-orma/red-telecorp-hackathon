# Registro de las decisiones iniciales del stack

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-13 23:50
- **Issue / PR**: #1
- **Rama**: docs/1-decisiones-iniciales

## Qué se hizo
- Se registraron las decisiones del equipo:
  - **D1** AWS Academy Learner Lab;
  - **D3** Serverless Framework;
  - **D4** Python;
  - **D6** `us-east-1`;
  - **D8** DynamoDB con tablas separadas.
- Se actualizaron `AGENTS.md` (§1 stack decidido; §7 reglas de Learner Lab: `LabRole`, credenciales temporales, nombres de recursos), `docs/arquitectura.md` y `docs/decisiones/README.md`.
- Se corrigió `.claude/settings.json`: la regla que impedía leer los `.env` también bloqueaba `.env.example`.

## Archivos y recursos tocados
- `docs/decisiones/` (4 archivos nuevos + README), `AGENTS.md`, `docs/arquitectura.md`, `.env.example`, `.claude/settings.json`. No se crearon recursos cloud.

## Decisiones tomadas
- [aws-academy-us-east-1](../decisiones/2026-11-13-aws-academy-us-east-1.md)
- [serverless-framework](../decisiones/2026-11-13-serverless-framework.md)
- [python-lambdas](../decisiones/2026-11-13-python-lambdas.md)
- [dynamodb-tablas-separadas](../decisiones/2026-11-13-dynamodb-tablas-separadas.md)

## Pendiente / siguiente paso
- **D2** segunda nube, **D5** frontend (se esperan ideas del equipo) y **D7** fórmulas: siguen abiertas.
- Verificar en Learner Lab qué servicios están disponibles: SES, SNS SMS, Secrets Manager, runtime `python3.12`, Step Functions con `LabRole`.
- Anotar la versión de Serverless Framework que usa el equipo en la decisión D3.

## Notas para los otros agentes
- **Nunca generes `iamRoleStatements` ni roles IAM**: en Learner Lab fallan. Siempre usa `LabRole`.
- El bloque GCP de la arquitectura **no está decidido**. No construyas nada contra GCP hasta que se cierre D2.
- El diseño de claves de DynamoDB es un borrador: revísalo antes de crear las tablas.
