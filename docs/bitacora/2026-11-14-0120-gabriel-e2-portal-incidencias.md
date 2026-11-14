# E2: Portal del usuario + gestión de incidencias

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 01:20
- **Issue / PR**: #15 (contrato #14 / PR #16)
- **Rama**: feat/15-e2-portal-incidencias

## Qué se hizo
- **Backend** (`services/api/src/incidencias.py`):
  - `POST /api/reportes`: valida, **deduplica con una clave condicional** (`usuario#zona` en la tabla `dedup`) y encola en SQS → `202`.
  - Worker SQS: put idempotente + historial `CREADO`.
  - `GET` de la lista y del detalle (historial + transiciones permitidas + estado de la zona).
  - `PATCH` de estado validado (409 si la transición no corresponde), con historial y liberación de la clave de deduplicación al resolver.
  - `GET /api/zonas/ubicar` decide la zona a partir de lat/lng.
- **Reglas** (`telecorp.reglas`): transiciones, validación del reporte y enmascarado de datos personales. **Geo** (`telecorp.zonas.ubicar`). 17 pruebas.
- **Frontend**:
  - router mínimo y navegación por pestañas;
  - **portal móvil** (tipo con íconos, GPS + mapa con pin arrastrable, zona detectada por el backend, datos recordados en el navegador);
  - **seguimiento** con progreso animado, estado de la zona e historial;
  - **panel de incidencias** (filtros por zona y estado, detalle, cambio de estado);
  - **mapa de calor** de reportes de 24 h en el centro de control.
- `scripts/demo/reportar.py`: genera reportes ficticios.

## Cómo probarlo
- `/portal` desde el celular → enviar → seguimiento.
- `/incidencias` → abrir → "Siendo atendida" → el seguimiento se actualiza en ≤4 s.
- `python scripts/demo/reportar.py <URL> --zona ZONA-05 --n 8` → mancha de calor en el mapa.

## Decisiones tomadas
- Enmienda de D8: tabla `dedup` con TTL (ver la decisión).

## Pendiente / siguiente paso
- E3: detección colectiva + Step Functions (la deduplicación ya garantiza "usuarios distintos").
- Autenticación del operador (Cognito está permitido en el lab: verificar). Por ahora, los datos se enmascaran.

## Notas para los otros agentes
- **SQS → Lambda con poco tráfico: NO uses `maximumBatchingWindow`**. Con ventana de 1 s la latencia era de 7–20 s (el poller espera su long polling); sin ventana y con `batchSize` 10, **~0.8 s**. El clasificador de antenas sí la usa, porque recibe ráfagas de 36.
- Consultar un GSI justo después de escribir **no es confiable** (consistencia eventual): para unicidad, usa un put condicional sobre la clave primaria.
- En Git Bash, `curl -d` con tildes manda latin-1: prueba el API con Python (`scripts/demo/reportar.py`).
- Los scripts Python que imprimen Unicode deben hacer `sys.stdout.reconfigure(encoding="utf-8")` (consola cp1252).
- Datos de demo actuales en `dev-gabriel`: 22 reportes ficticios (8 en ZONA-05).
