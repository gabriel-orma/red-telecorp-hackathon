# Stack `antenas`

```
EventBridge Scheduler (cada 1 min, APAGADO por defecto)
   → Lambda simulador ──(36 métricas × 4 lecturas/min)──► SQS metricas (+DLQ)
   → Lambda clasificador ─► DynamoDB metricas (serie, TTL 7 d)
                          ─► DynamoDB antenas (estado actual, Stream)
                          ─► historial (CAMBIO_ESTADO si cambió)
```

- **Clasificación** (`telecorp.reglas.clasificar_antena`): `0` → INHABILITADA, `<60` → CAIDA, `60–129` → NORMAL, `>129` → SATURADA.
- **Simulador**: tráfico base estable por antena + ciclo diario + ruido. Saturación ocasional (`probSaturacion`). Las **fallas forzadas** se leen de SSM `/telecorp/<stage>/simulador`.
- **Encender/apagar y forzar fallas**: desde el panel (botón "Simulador" y "Simular falla" en el detalle de cada antena) o por API:
  ```bash
  curl -X PUT $URL/api/simulador -d '{"activo": true}'
  curl -X PUT $URL/api/simulador -d '{"fallas": {"ANT-013": 0}}'      # inhabilitar
  curl -X PUT $URL/api/simulador -d '{"limpiarFallas": true}'
  ```
- **Costo**: apagado = $0. Encendido ≈ 50 s de Lambda de 256 MB por minuto (~$0.30/día). Apágalo al terminar.
- Pruebas: `python -m pytest services/antenas`.
