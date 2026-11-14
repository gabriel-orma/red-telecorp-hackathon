# Decisiones técnicas

Un archivo por decisión: `AAAA-MM-DD-<slug>.md`, con este formato:

```markdown
# <Decisión>
- Estado: propuesta | aceptada | reemplazada por <archivo>
- Issue: #
## Contexto
## Decisión
## Consecuencias (costo, rúbrica, qué cambia para cada módulo)
```

## Resumen

| # | Tema | Estado | Decisión |
|---|---|---|---|
| D1 | Cuentas AWS | ✅ aceptada | AWS Academy Learner Lab → [2026-11-13-aws-academy-us-east-1](2026-11-13-aws-academy-us-east-1.md) |
| D2 | Segunda nube | ⏳ abierta | Por definir. Propuesta inicial: GCP (Gemini + BigQuery + Looker Studio). Alternativa: Azure. |
| D3 | IaC | ✅ aceptada | Serverless Framework → [2026-11-13-serverless-framework](2026-11-13-serverless-framework.md) |
| D4 | Runtime de las Lambdas | ✅ aceptada | Python → [2026-11-13-python-lambdas](2026-11-13-python-lambdas.md) |
| D5 | Frontend | ✅ aceptada | React + Vite + Tailwind + shadcn/ui + MapLibre, en S3 + CloudFront → [2026-11-14-frontend](2026-11-14-frontend.md) |
| D6 | Región AWS | ✅ aceptada | `us-east-1` → [2026-11-13-aws-academy-us-east-1](2026-11-13-aws-academy-us-east-1.md) |
| D7 | Fórmula de prioridad y umbral de recurrencia | ⏳ abierta | Por definir. Ver `docs/arquitectura.md`, "Reglas de negocio". |
| D8 | Tablas DynamoDB | ✅ aceptada | Tablas separadas → [2026-11-13-dynamodb-tablas-separadas](2026-11-13-dynamodb-tablas-separadas.md) |

Las decisiones **abiertas no las resuelve un agente solo**: van por un issue `decision`. Mientras tanto, no construyas nada que dependa de ellas. Si no queda otra, deja un `TODO(D2)` o `TODO(D7)`.

| D9 | Cuentas de usuario | ✅ aceptada | Cognito + autorizador JWT, auto-confirmación → [2026-11-14-cuentas-cognito](2026-11-14-cuentas-cognito.md) |
| D10 | Estadísticas del estado público | ✅ aceptada | Contadores agregados de 15 min → [2026-11-14-estadisticas-agregadas](2026-11-14-estadisticas-agregadas.md) |

## Otras aceptadas
- [2026-11-13-coordinacion-por-issues](2026-11-13-coordinacion-por-issues.md)
