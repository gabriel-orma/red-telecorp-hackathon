# Stack `api`

Un único **HTTP API (HTTPS)** sirve los datos (`/api/*`) y el frontend (`/*`). Al compartir origen no hay CORS ni URL que inyectar en el build.

| Ruta | Función | Descripción |
|---|---|---|
| `GET /api/antenas` | `antenas.listar_antenas` | Catálogo + estado actual de las 36 antenas |
| `GET /api/zonas` | `antenas.listar_zonas` | Zonas con su peor estado, conteos y tráfico |
| `GET /api/antenas/{id}/metricas?minutos=30` | `antenas.metricas_antena` | Serie para el gráfico del detalle |
| `GET /api/simulador` | `simulador.obtener` | Estado del simulador y fallas forzadas |
| `PUT /api/simulador` | `simulador.actualizar` | `{activo}`, `{fallas: {ANT-x: gb\|null}}`, `{limpiarFallas}` |
| `GET /api/zonas/ubicar?lat=&lng=` | `antenas.ubicar_zona` | Zona de cobertura de un punto (404 si está fuera) |
| `POST /api/reportes` 🔒 | `incidencias.crear_reporte` | **Requiere sesión (Cognito)**. Cuerpo `{tipo, descripcion, ubicacion?}`; los datos personales salen del token. Zona por GPS o, si no, la de la cuenta. Deduplica y encola en SQS → `202` |
| `GET /api/mis-reportes` 🔒 | `incidencias.mis_reportes` | Reportes del usuario (GSI `usuario-fecha`) |
| `GET /api/estado?zonaId=` | `estado.estado` | Estado público: semáforo, serie de 24 h + base, tipos, zonas, incidentes (caché de 10 s) |
| `GET /api/config` | `estado.config` | Ids públicos de Cognito para el frontend |
| *(SQS `reportes`)* | `incidencias.registrar` | Worker: put idempotente + historial `CREADO`; los fallos van a la DLQ |
| `GET /api/incidencias?zonaId=&estado=&horas=` | `incidencias.listar` | Lista con datos personales enmascarados |
| `GET /api/incidencias/{id}` | `incidencias.obtener` | Detalle + historial + `transicionesPermitidas` + estado de la zona |
| `PATCH /api/incidencias/{id}/estado` | `incidencias.cambiar_estado` | `{estado, comentario}`; valida la transición (409 si no se permite) y libera la clave de deduplicación al resolverse |
| `GET /api/analitica?dias=7` | `analitica.analitica` | KPIs, zonas, antenas más problemáticas, tipos, duración y alcance de incidentes, recurrencia (caché de 60 s) |
| `POST /api/recurrencia` | `analitica.ejecutar_recurrencia` | Ejecuta ahora la Step Function de recurrencia |
| `GET /api/escenarios` | `escenarios.obtener` | Estado del escenario de demo (oleada, reportes, antenas) |
| `POST /api/escenarios` | `escenarios.lanzar` | `{tipo: TORMENTA o CORTE_ENERGIA, zonaId}` arranca la Step Function `escenario` (409 si ya hay uno en curso) |
| `POST /api/escenarios/reiniciar` | `escenarios.reiniciar` | Reiniciar demo: detiene el escenario, quita fallas, restablece y reanuda incidentes |
| `POST /api/colectivos/reanudar` | `colectivos.reanudar` | Reanuda incidentes cuya Step Function se detuvo (p. ej. al apagarse el lab) |
| `GET /`, `GET /{proxy+}` | `web.handler` | Frontend desde S3 privado (gzip + caché en memoria) |

**Ciclo de vida de una incidencia**: `REGISTRADA → EN_REVISION → EN_ATENCION → SOLUCIONADA → CERRADA`. Se pueden saltar pasos hacia adelante; la única vuelta atrás es reabrir (`SOLUCIONADA → EN_ATENCION`). La regla vive en `telecorp.reglas.transicion_valida`. Cada cambio queda en el historial inmutable.

**Privacidad**: aún no hay autenticación, así que el API **enmascara** DNI, número, email y teléfono (`70***456`, `g***@dominio`).

**¿Por qué una Lambda sirve el frontend?** CloudFront está bloqueado en Learner Lab (ver D1), y el S3 *static website* no tiene HTTPS, que la geolocalización y la voz del navegador necesitan. Los `assets/*` llevan hash y se cachean 1 año en el navegador, así que la Lambda casi solo entrega `index.html`.

La URL sale al final de `bash scripts/deploy.sh <stage>`, o con:
```bash
aws cloudformation describe-stacks --stack-name telecorp-api-<stage> --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text
```
