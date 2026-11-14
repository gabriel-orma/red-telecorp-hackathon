# Stack `workflows`: detección colectiva + Step Functions (E3)

```
incidencias (Stream, INSERT) ─┐
                              ├─► Lambda detector ──► crea el colectivo (candado por zona) ──► Step Function
antenas (Stream, filtro       │      · ≥10 usuarios DISTINTOS / zona / <24 h  (regla del enunciado)
  estado ∈ {CAIDA,            │      · antena entra en falla → detección proactiva
  INHABILITADA}) ─────────────┘      · si ya hay uno abierto en la zona → se suma (y avisa al nuevo)
```

## Step Function `telecorp-<stage>-incidente-colectivo`
Definición: [`statemachines/incidente-colectivo.yml`](statemachines/incidente-colectivo.yml)

| # | Estado | Tipo | Qué hace |
|---|---|---|---|
| 1 | Aviso "en evaluación" | **Map** | Un aviso por afectado (en la app + email SNS si el usuario lo aceptó) |
| 2 | Verificar infraestructura | Task | Correlaciona con las antenas de la zona |
| 3 | Priorizar | Task | `(afectados + 10 × antenas en falla) × criticidad de la zona` → BAJA/MEDIA/ALTA/CRÍTICA (**TODO D7**, pesos en SSM `/telecorp/<stage>/reglas`) |
| 4 | Resumir | Task + **Catch** | Resumen para el operador (plantilla; IA en E4). Si falla, el flujo sigue |
| 5 | Confirmar | Task | Colectivo → INCIDENCIA_CONFIRMADA; sus incidencias → EN_ATENCION |
| 6 | Aviso "incidencia en tu zona" | **Map** | |
| 7 | ¿Crítico? | **Choice** | Sí → publica en SNS `alertas-operador` (**integración directa** de Step Functions, sin Lambda) |
| 8 | Monitorear ↔ Re-verificar | **Wait** + Task + Choice | Cada `esperaVerificacionSegundos`: ¿antenas normalizadas? ¿el operador lo marcó? |
| 9 | Restablecer | Task | Colectivo → SERVICIO_RESTABLECIDO |
| 10 | Aviso "restablecido" | **Map** | |
| 11 | Cerrar | Task | Incidencias → SOLUCIONADA, duración registrada, candado de la zona liberado |

- Todos los Task tienen **Retry** con backoff exponencial (2 s × 2, 3 intentos).
- Si el monitoreo supera `maxIteraciones`, el flujo termina en **Fail** (`MonitoreoAgotado`) para atención manual.
- Cada paso actualiza `pasoActual` del colectivo: el panel dibuja el flujo con el paso en curso.

## Probar
```bash
python scripts/demo/reportar.py $URL --zona ZONA-05 --n 12        # → colectivo por reportes
curl -X PUT $URL/api/simulador -d '{"fallas": {"ANT-013": 0}}'   # → antena en falla: origen AMBOS, prioridad sube
curl -X PUT $URL/api/simulador -d '{"fallas": {"ANT-013": null}}' # → restablecimiento automático y cierre
```
O desde el panel: **Colectivos** → "Marcar servicio restablecido".

## Costos
- El detector solo se invoca con reportes nuevos o con antenas en falla (filtro del stream).
- Step Functions Standard: unas ~4 transiciones por re-verificación, que cuestan céntimos al día por incidente abierto.
