# E1: Mapa en vivo

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 01:00
- **Issue / PR**: #11 (contrato #10 / PR #12)
- **Rama**: feat/11-e1-mapa-en-vivo

## Qué se hizo
- **Contrato**: 12 zonas reales de Lima con centro, radio y clientes, y 36 antenas con lat/lng.
- **Stack `base`**: 5 tablas DynamoDB (on-demand + PITR), colas SQS `reportes` y `metricas` con DLQ, SSM `/telecorp/<stage>/simulador`, Secrets Manager `telecorp/<stage>/ia` y el layer `comun` (`telecorp.*`).
- **Stack `antenas`**: simulador (EventBridge Scheduler, apagado por defecto, 4 lecturas/min, episodios de saturación de ~6 min) y clasificador (SQS → `metricas` + `antenas` + historial de cambios de estado, con respuesta parcial de lote).
- **Stack `api`**: HTTP API con `/api/antenas`, `/api/zonas`, `/api/antenas/{id}/metricas`, `GET`/`PUT /api/simulador`, y el **frontend servido por HTTPS** desde un S3 privado mediante la Lambda `web` (CloudFront bloqueado).
- **Frontend** (React + Vite + Tailwind v4 + MapLibre v6 + Framer Motion):
  - mapa oscuro con zonas de cobertura y antenas de color, con pulso en las que fallan;
  - KPIs animados, zonas ordenadas por gravedad;
  - detalle de antena con un gráfico de 30 min y los botones "Simular falla";
  - interruptor del simulador; vista móvil.
- `scripts/deploy.sh` (por componentes) y `scripts/remove.sh` (vacía los buckets versionados). `pytest.ini` con 13 pruebas.

## Cómo probarlo
```bash
bash scripts/deploy.sh dev-<alias>     # imprime la URL
python -m pytest
```
En la URL: encender el simulador → clic en una antena → "Caída" → la antena se pone roja con pulso y la zona sube en la lista.

## Decisiones tomadas
- Enmienda de D8: nueva tabla `antenas`; `metricas` sin GSI.
- Frontend servido por la Lambda `web` en el mismo origen que el API (sin CORS).

## Pendiente / siguiente paso
- Feedback de diseño del equipo, y luego E2 (portal del usuario + incidencias).

## Notas para los otros agentes
- **maplibre v6**: requiere `setWorkerUrl` con `maplibre-gl-worker.mjs?url` (ya está en `MapaRed.tsx`), y la Lambda `web` debe servir `.mjs` como `application/javascript`.
- maplibre fuerza `position: relative` en su contenedor: posiciona un div externo.
- El *event source mapping* de SQS tarda ~1 min en activarse tras el primer despliegue: las primeras métricas pueden demorar.
- `index.html` se cachea 15 s en la Lambda caliente; tras publicar, recarga después de unos segundos.
- Las capturas del navegador integrado de Claude a veces muestran un frame viejo: verifica con `get_page_text`.
