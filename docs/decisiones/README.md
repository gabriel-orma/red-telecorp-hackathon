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

## Decisiones abiertas (resolver por un issue `decision` antes de construir encima)

| # | Tema | Opciones / notas |
|---|---|---|
| D1 | Cuentas AWS | ¿AWS Academy Learner Lab o cuentas personales? En Learner Lab no se pueden crear roles IAM (se usa `LabRole`) y SES/SNS SMS pueden estar limitados. |
| D2 | Segunda nube | Propuesta: GCP (Gemini + BigQuery + Looker Studio). Alternativa: Azure. |
| D3 | IaC | AWS SAM / Serverless Framework / Terraform (Terraform cubre AWS y GCP a la vez). |
| D4 | Runtime de las Lambdas | Python / Node.js (TypeScript). Uno solo para todo el equipo. |
| D5 | Frontend | Framework y hosting (S3 + CloudFront o Firebase Hosting). |
| D6 | Región AWS y proyecto GCP | Ej.: `us-east-1` (obligatoria en Learner Lab). |
| D7 | Fórmula de prioridad y umbral de recurrencia | Ver `docs/arquitectura.md`, "Reglas de negocio". |
| D8 | Diseño de las tablas DynamoDB | Una sola tabla o varias; claves y GSI para la consulta por zona y ventana de 24 h. |

## Aceptadas
- [2026-11-13-coordinacion-por-issues](2026-11-13-coordinacion-por-issues.md)
