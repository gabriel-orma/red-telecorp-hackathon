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
| 7 | Monitorear ↔ Re-verificar | **Wait** + Task + Choice | Cada `esperaVerificacionSegundos` (300): restablecido / agotado / **escalar** (la falla apareció después) |
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

## Configuración (SSM `/telecorp/<stage>/reglas` → `colectivo`)
`esperaVerificacionSegundos` 300 · `maxIteraciones` 2000 · `maxMonitoreoMinutos` 2880 · `cierreSinReportesMinutos` 60 · `loteAvisos` 50.
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
- Step Functions Standard: cada vuelta de monitoreo son ~9 eventos y 3 transiciones. Con espera de 300 s son ~864 transiciones
  al día por incidente abierto (≈0,02 USD/día); con 30 s eran 8.640 (≈0,22 USD/día). El nivel gratuito cubre 4.000/mes.
