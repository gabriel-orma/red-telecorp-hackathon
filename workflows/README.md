# Stack `workflows`: detección colectiva + Step Functions (E3)

```
incidencias (Stream, INSERT) ─┐
                              ├─► Lambda detector ──► crea el colectivo (candado por zona) ──► Step Function
antenas (Stream, filtro       │      · ≥10 usuarios DISTINTOS / zona / <24 h  (regla del enunciado)
  estado ∈ {CAIDA,            │      · antena entra en falla → detección proactiva
  INHABILITADA}) ─────────────┘      · si ya hay uno abierto en la zona → se suma (y avisa al nuevo)
```

## Step Function `telecorp-<stage>-incidente-colectivo`
Definición: [`statemachines/incidente-colectivo.yml`](statemachines/incidente-colectivo.yml) (el grafo está resumido en su cabecera).

| # | Estado | Tipo | Qué hace |
|---|---|---|---|
| 1 | Aviso "en evaluación" | Task + **Map por lotes** | `PrepararAviso` devuelve lotes de 50; cada iteración del Map avisa a un lote (app + email SNS) |
| 2 | Verificar infraestructura | Task | Correlaciona con las antenas de la zona (**CAÍDA, INHABILITADA y SATURADA**) |
| 3 | Priorizar | Task | `(afectados + 10 × antenas en falla) × criticidad de la zona` → BAJA/MEDIA/ALTA/CRÍTICA (**TODO D7**, pesos en SSM `/telecorp/<stage>/reglas`) |
| 4 | Resumir | Task + **Catch** | Resumen para el operador (plantilla; **HOOK de la IA en la 2.ª nube**). Si falla, el flujo sigue |
| 5 | **¿Hay falla?** | **Choice** | La verificación decide cómo se informa: |
| 5a | → con falla | Task + Map | Colectivo → INCIDENCIA_CONFIRMADA, incidencias → EN_ATENCION, aviso "identificamos una incidencia" |
| 5b | → sin falla | Task + Map | Aviso honesto "seguimos evaluando" (**nunca** "falla confirmada"); el colectivo sigue EN_EVALUACION |
| 6 | ¿Crítico? | **Choice** | Sí → SNS `alertas-operador` (**integración directa**, sin Lambda; si falla, el ciclo sigue) |
| 7 | Monitorear ↔ Re-verificar | **Wait** + Task + Choice | Cada `esperaVerificacionSegundos` (30): restablecido / agotado / **escalar** (la falla apareció después) |
| 8 | Restablecer → aviso → Cerrar | Task + Map + Task | Incidencias → SOLUCIONADA, duración registrada, zona liberada; **el cierre avisa a los rezagados** |
| 9 | Replicar a la 2.ª nube | Task + **Catch** | **HOOK** (hoy no hace nada); si falla no bloquea el cierre |

**Cuándo se restablece** (reglas puras en [`src/monitoreo.py`](src/monitoreo.py), con casos límite en `tests/`):
1. el operador lo marcó; o
2. el colectivo tuvo antenas en falla y **todas** ya no están degradadas; o
3. **no tuvo antenas** (nació de reportes con la red normal) y no entró ningún reporte nuevo en la zona durante
   `cierreSinReportesMinutos` (60). Antes este colectivo nunca terminaba.

**Fallos y límites** (Standard: 25.000 eventos de historial y 256 KiB por estado):
- Todos los Task tienen `Retry`, `Catch` y `TimeoutSeconds`; la máquina tiene `TimeoutSeconds` global (60 h).
- Un error irrecuperable de un paso crítico va a `ManejarFallo`: el colectivo pasa a **REQUIERE_ATENCION**, se libera la zona
  y la ejecución termina en `Fail` (`FalloEnFlujo`). Lo mismo si el monitoreo se agota (`MonitoreoAgotado`).
- Monitoreo acotado por `maxIteraciones` (2000 × 9 eventos = 18.000) **y** por `maxMonitoreoMinutos` (48 h).
- Avisos por lotes: 7 eventos por lote de 50 → 10.000 afectados ≈ 4.200 eventos en los 3 avisos (cálculo, no medido en AWS).
  El tope real pasa a ser el ítem del colectivo en DynamoDB: medido ≈ 34 B por afectado en JSON (400 KB ≈ 12.000; con la
  sobrecarga de DynamoDB, del orden de 10.000), y el tiempo de `confirmar`/`cerrar` (Lambda de 300 s, **sin medir**).
- **Avisos idempotentes**: `telecorp.notificador.notificar` marca `(incidencia, estado)` en `dedup` (`AVISO#...`, TTL 7 días)
  antes de enviar; un reintento o el aviso inmediato al sumarse no duplican correo, historial ni contador.
- Cada paso actualiza `pasoActual` del colectivo: el panel dibuja el flujo con el paso en curso.

## Step Function `telecorp-<stage>-escenario` (E5)
Definición: [`statemachines/escenario.yml`](statemachines/escenario.yml). Entrada `{tipo: TORMENTA | CORTE_ENERGIA, zonaId}`.

| Estado | Tipo | Qué hace |
|---|---|---|
| Preparar | Task | Planifica las oleadas (`telecorp.escenarios.planificar`), enciende el simulador y publica el estado en SSM |
| Oleadas | **Map** secuencial (MaxConcurrency 1) | Por oleada: **Wait** de 12 s, luego fuerza fallas de antenas y envía reportes de vecinos ficticios por el mismo camino que un reporte real (candado de deduplicación + SQS) |
| Finalizar | Task | Marca el escenario como terminado (también si algo falla, vía Catch) |

- **Tormenta**: la zona elegida y sus vecinas (radio de 5,5 km); antenas caídas o saturadas.
- **Corte de energía**: solo la zona; sus antenas se apagan (0 GB/min) una a una.
- **Reiniciar demo** (`POST /api/escenarios/reiniciar`): detiene el escenario, quita las fallas y marca como restablecidos los incidentes abiertos; sus Step Functions los cierran en segundos.
- **Modo reanudar** de `incidente-colectivo`: `{reanudar: true}` entra directo al monitoreo. Lo usan `POST /api/colectivos/reanudar` y `scripts/reactivar-lab.sh`.

## Step Function `telecorp-<stage>-recurrencia` (E6)
Definición: [`statemachines/recurrencia.yml`](statemachines/recurrencia.yml). Se ejecuta **todos los días a las 06:00 (America/Lima)** con EventBridge Scheduler, y a pedido desde la analítica (`POST /api/recurrencia`).

| Estado | Tipo | Qué hace |
|---|---|---|
| ContarFallas | Task | Por antena, cuenta las entradas en falla (caída o inhabilitada) en la ventana según el historial; desmarca las que ya no superan el umbral |
| HayEstructurales | **Choice** | ¿Alguna supera el umbral? |
| MarcarEstructurales | **Map** (5 en paralelo) | Marca `estructural` en la antena; si es nueva: historial `MARCADO_ESTRUCTURAL` + alerta SNS al NOC |
| Resumen | Task | Guarda la última ejecución en SSM |

Umbral provisional (TODO D7): **3 fallas en 7 días**, en SSM `/telecorp/<stage>/reglas` → `recurrencia`.

**Prioridad con tiempo activo (E6)**: el paso de re-verificación recalcula el puntaje en cada vuelta (`afectados × criticidad × (1 + 0,25 × horas activo)` + antenas en falla). Solo deja historial cuando cambia el nivel.

## Configuración (SSM `/telecorp/<stage>/reglas` → `colectivo`)
`esperaVerificacionSegundos` 30 · `maxIteraciones` 2000 · `maxMonitoreoMinutos` 2880 · `cierreSinReportesMinutos` 60 · `loteAvisos` 50.
Para una demo en vivo baja `esperaVerificacionSegundos` a 10–15 y `cierreSinReportesMinutos` a 1–2 (y vuelve a subirlos después).

## Pendiente
- Máquina `recurrencia-diaria` (EventBridge Scheduler → Lambda → [`src/recurrencia.py`](src/recurrencia.py), regla ya probada) y
  decidir dónde se marca `ESTRUCTURAL`.
- Cierre/confirmación por lotes (hoy `_mover_incidencias` recorre todas las incidencias en una Lambda de 300 s).
- Los hooks de la 2.ª nube (`resumir`, `replicarNube2`) siguen sin implementar.
- `loggingConfig` de la máquina sin verificar en AWS (¿permite `LabRole` la entrega de logs?).

## Probar
```bash
pytest                                                             # reglas puras y estructura de la máquina (sin AWS)
python scripts/demo/reportar.py $URL --zona ZONA-05 --n 12        # → colectivo por reportes
curl -X PUT $URL/api/simulador -d '{"fallas": {"ANT-013": 0}}'   # → antena en falla: origen AMBOS, prioridad sube
curl -X PUT $URL/api/simulador -d '{"fallas": {"ANT-013": null}}' # → restablecimiento automático y cierre
```
O desde el panel: **Colectivos** → "Marcar servicio restablecido".

## Costos
- El detector solo se invoca con reportes nuevos o con antenas en falla (filtro del stream).
- Step Functions Standard: cada vuelta de monitoreo son ~9 eventos y 3 transiciones. Con la espera de 30 s (la de la demo: «Reiniciar
  demo» y «restablecer» responden en segundos) son ~8.640 transiciones al día por incidente abierto (≈0,22 USD/día) y el tope de
  2.000 vueltas lo limita a ≈17 h (≈0,15 USD por incidente). Con 300 s costaría 10 veces menos, pero restablecer tardaría hasta
  5 min: si un stage va a quedar días con incidentes abiertos, súbela en SSM (`/telecorp/<stage>/reglas`). El nivel gratuito cubre 4.000/mes.
