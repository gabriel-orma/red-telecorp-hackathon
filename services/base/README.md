# Stack `base`

Datos y recursos compartidos. No tiene lógica de negocio. Se despliega primero (`scripts/deploy.sh` lo hace).

| Recurso | Nombre | Para qué |
|---|---|---|
| DynamoDB `incidencias` | `telecorp-<stage>-incidencias` | Reportes de usuarios (GSI `zona-fecha`, Stream) |
| DynamoDB `historial` | `telecorp-<stage>-historial` | Eventos inmutables (PK `entidadId`, SK `sk`) |
| DynamoDB `metricas` | `telecorp-<stage>-metricas` | Serie de tráfico por antena (TTL de 7 días en `expiraEn`) |
| DynamoDB `antenas` | `telecorp-<stage>-antenas` | Estado actual de cada antena (Stream) |
| DynamoDB `colectivos` | `telecorp-<stage>-colectivos` | Incidentes colectivos (GSI `zona-estado`) |
| SQS `reportes` / `metricas` | `+ -dlq` | Colchón anti-avalancha; 3 reintentos → DLQ (14 días) |
| SSM | `/telecorp/<stage>/simulador` | Fallas forzadas y parámetros del simulador |
| Secrets Manager | `telecorp/<stage>/ia` | API key de la IA (2.ª nube, D2) |
| Lambda Layer `comun` | `telecorp-<stage>-comun` | Paquete Python `telecorp.*` (ver `layer/python/telecorp/__init__.py`) |

Todas las tablas son on-demand y tienen **PITR** (restauración a cualquier segundo de los últimos 35 días).

`layer/python/telecorp/zonas.json` **no se versiona**: `scripts/deploy.sh` lo copia desde `contracts/zonas.json` en cada despliegue.
