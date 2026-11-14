# Arquitectura

> **Estado: propuesta base.** Es el punto de partida acordado para que todos los agentes diseñen sobre lo mismo. Para cambiar algo de aquí, abre un issue `decision` y registra el resultado en `docs/decisiones/`.
>
> **Ya decidido:** AWS Academy Learner Lab (`LabRole`), `us-east-1`, Serverless Framework, Python y DynamoDB con tablas separadas.
> **Por definir:** la segunda nube (el bloque GCP del diagrama es solo la **propuesta inicial**), el frontend y la fórmula de prioridad. Ver [`decisiones/README.md`](decisiones/README.md).

## Vista general

```
                          ┌──────────────────────── AWS ─────────────────────────────────────────┐
[Portal usuario] ──HTTPS──► API Gateway (HTTP API) ─► Lambda API ─► SQS reportes (+DLQ) ─► Lambda ─┐
[Panel operador] ─────────►        │                                                               │
                                   └─ consultas / cambios de estado ──────────────────────────────►│
                                                                                                   ▼
[Simulador antenas] ─ EventBridge Scheduler ─► Lambda ─► SQS métricas (+DLQ) ─► Lambda clasificador ─► DynamoDB
                                                                (tablas separadas, PITR, on-demand, multi-AZ)
                                                                                         │ DynamoDB Streams
                                                                                         ▼
                                                    Lambda detector (regla de 10 usuarios/zona/24 h,
                                                                     antena caída o inhabilitada)
                                                                                         ▼
                                        Step Functions ─ Incidente colectivo:
                                          correlacionar con antenas → priorizar → IA (resumen/clasificación)
                                          → notificar (SNS SMS / SES email) → esperar técnico (task token)
                                          → notificar "restablecido" → cerrar
                                        Step Functions ─ Recurrencia (diaria, EventBridge Scheduler)
                                                                                         │
  Secrets Manager / SSM: API keys y credenciales de GCP                                  │
                          └───────────────────────────────────────────────────────────────┼──────────┘
                          ┌──────────────────────── GCP ───────────────────────────────── ▼ ────────┐
                          │  Gemini (Vertex AI / API): clasificar el texto libre, resumir incidentes │
                          │  BigQuery: histórico analítico (2.ª copia de los datos)                   │
                          │  Looker Studio: dashboards de zonas, antenas, tipos y duración            │
                          │  (opcional) Firebase Hosting para el frontend                             │
                          └───────────────────────────────────────────────────────────────────────────┘
```

## Por qué así (relación con la rúbrica)

| Decisión | Motivo |
|---|---|
| SQS + DLQ delante de todo lo que escribe | Absorbe picos sin perder registros; las Lambdas escalan solas |
| DynamoDB on-demand + PITR | Serverless, multi-AZ por defecto, pago por uso, respaldo continuo |
| DynamoDB Streams → detector | Reacción en tiempo casi real sin polling |
| Step Functions | Flujos con estados, esperas y reintentos (incidente colectivo, recurrencia) |
| GCP: BigQuery + Gemini | 2.ª nube con rol real: analítica e IA. Además, copia de los datos en otra nube |
| Secrets Manager / SSM | Requisito explícito de la rúbrica |
| EventBridge Scheduler | Simulador y tareas periódicas sin servidores encendidos |

## Reglas de negocio (fuente de verdad)

- **Clasificación de antena** por GB/min: `0` → `INHABILITADA`; `<60` → `CAIDA`; `60..129` → `NORMAL`; `>129` → `SATURADA`.
- **Estados de incidencia**: `REGISTRADA → EN_REVISION → EN_ATENCION → SOLUCIONADA → CERRADA`. Cada transición genera un evento de historial.
- **Incidente colectivo**: al menos 10 `usuarioId` distintos con reportes en la misma `zonaId` en una ventana de menos de 24 h.
- **Prioridad**: función de los afectados, la criticidad de la zona (`contracts/zonas.json`) y las antenas en falla. La fórmula exacta va en `docs/decisiones/`.
- **Recurrencia**: umbral pendiente de decisión (sugerencia: 3 o más incidentes de la misma antena en 7 días → `ESTRUCTURAL`).

## Decisiones abiertas

Ver [`docs/decisiones/README.md`](decisiones/README.md). **Nadie las resuelve solo**: van por un issue `decision`.

## Inventario de recursos

> Actualízalo en el mismo PR que crea el recurso. Formato: `telecorp-<stage>-<nombre>`.

| Recurso | Nube / servicio | Nombre | Módulo | Notas |
|---|---|---|---|---|
| Tabla `incidencias` (GSI `zona-fecha`, Stream, PITR) | AWS DynamoDB | `telecorp-<stage>-incidencias` | base | E1 crea; se usa desde E2 |
| Tabla `historial` (PITR) | AWS DynamoDB | `telecorp-<stage>-historial` | base | Solo inserciones |
| Tabla `metricas` (TTL 7 d, PITR) | AWS DynamoDB | `telecorp-<stage>-metricas` | base | Serie por antena |
| Tabla `antenas` (Stream, PITR) | AWS DynamoDB | `telecorp-<stage>-antenas` | base | Estado actual |
| Tabla `colectivos` (GSI `zona-estado`, PITR) | AWS DynamoDB | `telecorp-<stage>-colectivos` | base | Se usa desde E3 |
| Tabla `dedup` (TTL 24 h) | AWS DynamoDB | `telecorp-<stage>-dedup` | base | Clave condicional `usuario#zona` (E2) |
| Colas `reportes`, `metricas` + DLQ | AWS SQS | `telecorp-<stage>-{reportes,metricas}[-dlq]` | base | 3 reintentos → DLQ (14 d) |
| Parámetro del simulador | AWS SSM | `/telecorp/<stage>/simulador` | base | Fallas forzadas |
| Secreto de IA | AWS Secrets Manager | `telecorp/<stage>/ia` | base | Placeholder hasta D2 |
| Layer Python común | AWS Lambda | `telecorp-<stage>-comun` | base | `telecorp.*` |
| Simulador + programación | AWS Lambda + EventBridge Scheduler | `telecorp-<stage>-simulador` | antenas | Apagado por defecto |
| Clasificador | AWS Lambda (SQS) | `telecorp-<stage>-clasificador` | antenas | Respuesta parcial de lote |
| HTTP API | AWS API Gateway v2 | `telecorp-<stage>-api` | api | `/api/*` + frontend |
| Bucket del frontend (versionado, privado) | AWS S3 | `telecorp-api-<stage>-bucketfrontend-*` | api | Servido por la Lambda `web` (CloudFront bloqueado) |
