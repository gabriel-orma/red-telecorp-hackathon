# Stack `api`

Un único **HTTP API (HTTPS)** sirve los datos (`/api/*`) y el frontend (`/*`). Al compartir origen no hay CORS ni URL que inyectar en el build.

| Ruta | Función | Descripción |
|---|---|---|
| `GET /api/antenas` | `antenas.listar_antenas` | Catálogo + estado actual de las 36 antenas |
| `GET /api/zonas` | `antenas.listar_zonas` | Zonas con su peor estado, conteos y tráfico |
| `GET /api/antenas/{id}/metricas?minutos=30` | `antenas.metricas_antena` | Serie para el gráfico del detalle |
| `GET /api/simulador` 🛡️ | `simulador.obtener` | Estado del simulador y fallas forzadas |
| `PUT /api/simulador` 🛡️ | `simulador.actualizar` | `{activo: bool}`, `{fallas: {ANT-x: 0–1000 \|null}}`, `{limpiarFallas}`. Valida todo antes de tocar nada (`nan`/`inf`/tipos → 400) |
| `GET /api/zonas/ubicar?lat=&lng=` | `antenas.ubicar_zona` | Zona de cobertura de un punto (404 si está fuera) |
| `POST /api/reportes` 🔒 | `incidencias.crear_reporte` | **Requiere sesión (Cognito)**. Cuerpo `{tipo, descripcion, ubicacion?}`; los datos personales salen del token. Zona por GPS o, si no, la de la cuenta. Deduplica y encola en SQS → `202` |
| `GET /api/mis-reportes` 🔒 | `incidencias.mis_reportes` | Reportes del usuario (GSI `usuario-fecha`) |
| `GET /api/estado?zonaId=` | `estado.estado` | Estado público: semáforo, serie de 24 h + base, tipos, zonas, incidentes (caché de 10 s) |
| `GET /api/config` | `estado.config` | Ids públicos de Cognito para el frontend |
| *(SQS `reportes`)* | `incidencias.registrar` | Worker: put idempotente + historial `CREADO`; los fallos van a la DLQ |
| `GET /api/incidencias?zonaId=&estado=&horas=` | `incidencias.listar` | **Vista pública** (lista blanca: estado, tipo, zona y fechas; sin nombre, GPS, descripción ni contacto) |
| `GET /api/incidencias/{id}` | `incidencias.obtener` | Detalle público + historial + `transicionesPermitidas` + estado de la zona |
| `GET /api/operador/incidencias[/{id}]` 🛡️ | `incidencias.listar_operador` / `obtener_operador` | Lo mismo **con el detalle del reporte** (nombre, ubicación, descripción); DNI, servicio, correo y teléfono salen enmascarados |
| `PATCH /api/incidencias/{id}/estado` 🛡️ | `incidencias.cambiar_estado` | `{estado, comentario}`; valida la transición (409 si no se permite) y libera la clave de deduplicación al resolverse. El historial guarda `operador:<sub>` |
| `wss://…/<stage>` | `tiempo_real.conectar / desconectar / mensaje` | WebSocket del panel. El servidor solo envía `{tipo: antenas, colectivos o incidencias}`; el panel vuelve a pedir esos datos |
| *(DynamoDB Streams)* | `tiempo_real.difundir` | Un aviso por tipo y lote (antenas: máx. 1 cada 2 s); `GoneException` → borra la conexión |
| `GET /api/linea-tiempo?horas=1` | `linea_tiempo.linea_tiempo` | Datos para "rebobinar" la red (0.1–24 h): reportes con punto, estado inicial y cambios de cada antena, colectivos con sus cambios de estado y prioridad. El navegador calcula el estado en cada instante |
| `GET /api/analitica?dias=7&datos=operativos` | `analitica.analitica` | KPIs, zonas, antenas más problemáticas, tipos, duración y alcance de incidentes, recurrencia (caché de 60 s). `datos=operativos` (por defecto) o `simulados`: **un universo por vez** (D13); `400` con otro valor |
| `POST /api/recurrencia` 🛡️ | `analitica.ejecutar_recurrencia` | Ejecuta ahora la Step Function de recurrencia. Cuerpo opcional `{"simulados": true}`: evalúa las fallas simuladas (no alerta al NOC) |
| `GET /api/escenarios` | `escenarios.obtener` | Estado del escenario de demo (oleada, reportes, antenas) |
| `POST /api/escenarios` 🛡️ | `escenarios.lanzar` | `{tipo: TORMENTA o CORTE_ENERGIA, zonaId}` arranca la Step Function `escenario` (409 si ya hay uno en curso) |
| `POST /api/escenarios/reiniciar` 🛡️ | `escenarios.reiniciar` | Reiniciar demo: detiene el escenario, quita fallas y restablece **solo los incidentes simulados** (los reales no se tocan) |
| `POST /api/colectivos/reanudar` 🛡️ | `colectivos.reanudar` | Reanuda incidentes cuya Step Function se detuvo (p. ej. al apagarse el lab) |
| `GET /`, `GET /{proxy+}` | `web.handler` | Frontend desde S3 privado (gzip + caché en memoria) |

**Ciclo de vida de una incidencia**: `REGISTRADA → EN_REVISION → EN_ATENCION → SOLUCIONADA → CERRADA`. Se pueden saltar pasos hacia adelante; la única vuelta atrás es reabrir (`SOLUCIONADA → EN_ATENCION`). La regla vive en `telecorp.reglas.transicion_valida`. Cada cambio queda en el historial inmutable.

**Acceso**: 🔒 = requiere sesión (ID token de Cognito); 🛡️ = requiere además el grupo **`operadores`**. Dos capas que deben coexistir: el autorizador JWT de `serverless.yml` valida el token y `src/acceso.py` (`@solo_operadores`) comprueba el claim `cognito:groups` en el handler (un autorizador JWT no puede mirar grupos). Sin sesión → 401; sesión sin rol → 403. `GET /api/colectivos/{id}` y `POST /api/colectivos/{id}/restablecer` también son 🛡️.

**Identidad**: el `usuarioId` de un reporte es el **`sub`** del token, nunca `custom:dni` (el usuario puede editar su DNI, no su `sub`). El DNI es solo un dato de perfil.

**Privacidad (R3)**: sin sesión solo sale una lista blanca de campos. El operador ve el detalle, pero DNI/servicio/correo/teléfono enmascarados (`70***56`, `g***@dominio`: ≤ 4 de 8 dígitos visibles). La vista pública del historial muestra `OPERADOR`, no el `sub`.

### Operadores
**Atajo:** `bash scripts/crear-operador.sh <stage> <correo>` crea el usuario confirmado, le pone una contraseña (guardada en `scripts/demo/.operador-<stage>.local`, ignorado por git) y lo agrega al grupo. Lo de abajo es el paso manual equivalente.

Se crean desde cuentas normales (se registran en el portal) y un humano con credenciales del Lab las agrega al grupo; después deben **volver a iniciar sesión** para que su token traiga el grupo:
```bash
POOL=$(aws cloudformation describe-stacks --stack-name telecorp-base-<stage> --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text)
aws cognito-idp admin-add-user-to-group --user-pool-id "$POOL" --username <correo> --group-name operadores
```
(Comando sin verificar contra el Learner Lab: si `admin-add-user-to-group` está bloqueado, usar la consola de Cognito → Grupos → `operadores` → Agregar usuario.) El grupo lo crea el stack `base` (`GrupoOperadores`).

**¿Por qué una Lambda sirve el frontend?** CloudFront está bloqueado en Learner Lab (ver D1), y el S3 *static website* no tiene HTTPS, que la geolocalización y la voz del navegador necesitan. Los `assets/*` llevan hash y se cachean 1 año en el navegador, así que la Lambda casi solo entrega `index.html`.

La URL sale al final de `bash scripts/deploy.sh <stage>`, o con:
```bash
aws cloudformation describe-stacks --stack-name telecorp-api-<stage> --query "Stacks[0].Outputs[?OutputKey=='Url'].OutputValue" --output text
```
