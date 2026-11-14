# Stack `api`

Un único **HTTP API (HTTPS)** sirve los datos (`/api/*`) y el frontend (`/*`). Al compartir origen no hay CORS ni URL que inyectar en el build.

| Ruta | Función | Descripción |
|---|---|---|
| `GET /api/antenas` | `antenas.listar_antenas` | Catálogo + estado actual de las 36 antenas |
| `GET /api/zonas` | `antenas.listar_zonas` | Zonas con su peor estado, conteos y tráfico |
| `GET /api/antenas/{id}/metricas?minutos=30` | `antenas.metricas_antena` | Serie para el gráfico del detalle |
| `GET /api/simulador` | `simulador.obtener` | Estado del simulador y fallas forzadas |
| `PUT /api/simulador` | `simulador.actualizar` | `{activo}`, `{fallas: {ANT-x: gb\|null}}`, `{limpiarFallas}` |
| `GET /`, `GET /{proxy+}` | `web.handler` | Frontend desde S3 privado (gzip + caché en memoria) |

**¿Por qué una Lambda sirve el frontend?** CloudFront está bloqueado en Learner Lab (ver D1), y el S3 *static website* no tiene HTTPS, que la geolocalización y la voz del navegador necesitan. Los `assets/*` llevan hash y se cachean 1 año en el navegador, así que la Lambda casi solo entrega `index.html`.

La URL sale al final de `bash scripts/deploy.sh <stage>`, o con:
```bash
aws cloudformation describe-stacks --stack-name telecorp-api-<stage> --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text
```
