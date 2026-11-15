# D13: Datos simulados y datos operativos viven separados

- Estado: aceptada (pendiente de OK del equipo)
- Issue: PR de la fase final (ver bitácora `2026-11-15-1600-rodrigo-fase-final`)

## Contexto
La demo necesita datos simulados (escenarios Tormenta / Corte de energía / Acelerada, fallas forzadas del simulador, vecinos ficticios) que pasan por **la misma tubería** que los reales: detector, estadísticas, analítica, recurrencia, avisos. Antes, esos datos se mezclaban con los operativos y los contaminaban:

- 9 reportes reales + 1 simulado en la misma zona formaban un colectivo falso, y una Tormenta ocupaba el candado de la zona y **bloqueaba** la detección de un colectivo real.
- Las fallas forzadas de antenas contaban como fallas en la analítica y podían marcar una antena como **estructural** y alertar al NOC.
- Los contadores del estado público y los KPI de la analítica incluían los reportes ficticios.
- «Reiniciar demo» marcaba como restablecidos **todos** los incidentes abiertos, también los de usuarios reales.

## Decisión
Una sola definición: `reglas.es_simulado(x)` (incidencia con `reporte.simulado`, colectivo con `simulado`, antena con `simulada`, evento de historial con `simulado`). El cliente no puede declararla: `construir_reporte` descarta el campo.

| Pieza | Comportamiento |
|---|---|
| Simulador / clasificador | Las lecturas de fallas **forzadas** llevan `simulada: true`; el clasificador lo guarda en la antena y en su evento `CAMBIO_ESTADO` |
| Detector | Cada universo tiene su **ventana** (`VENTANA#<zona>` / `VENTANA#<zona>~SIM`) y su **candado** (`LOCK#COLECTIVO#<zona>` / `…~SIM`). Cuenta usuarios distintos solo dentro de su universo; el reconciliador barre ambos |
| Colectivo | Se marca `simulado: true`; sigue el flujo completo (Step Functions, avisos de la app, análisis), pero se etiqueta «Simulado» |
| Estadísticas | Los reportes simulados incrementan series `SIM#GLOBAL` / `SIM#ZONA-xx`; el estado público y la analítica operativa leen solo `GLOBAL` / `ZONA-xx` |
| Analítica | `GET /api/analitica?datos=operativos` (por defecto) o `datos=simulados`: un universo por vez, nunca mezclados |
| Recurrencia | Cada ejecución evalúa un universo (`{"simulados": true}` en la manual). Una simulación marca la antena como estructural-simulada y **no alerta al NOC**; la ejecución operativa no toca esa marca |
| Estado público | Los colectivos simulados no mueven el semáforo; la respuesta incluye `simulacion.colectivosAbiertos` y la página avisa «hay una simulación en curso» |
| Reiniciar demo | Cierra **solo** los colectivos simulados |
| Alertas SNS | Un escalamiento a CRÍTICO de un colectivo simulado lleva el prefijo `[SIMULACION]` |

No se borra ni se reescribe ningún dato existente. Los datos de demo siguen consultables (selector «Simulación» en la analítica, etiqueta «Simulado»).

## Alternativas descartadas
- **Filtrar al leer** (sin separar ventanas y candados): no evita que lo simulado bloquee o complete un colectivo real.
- **Tablas o stages distintos para la demo**: duplica recursos y costo, y la demo dejaría de ejercitar la tubería real (lo que se quiere demostrar).
- **No contar la simulación en absoluto**: la demo perdería su valor (el panel quedaría vacío durante la presentación).

## Consecuencias
- Lo operativo es fiel: 10 usuarios reales siguen siendo 10; una Tormenta no cambia ninguna cifra del estado público ni de la analítica operativa.
- **Límite conocido**: los contadores y el historial **anteriores** a este cambio no se reclasifican (los contadores son agregados). En un stage ya usado para pruebas, la vista «Operativos» puede incluir datos de prueba antiguos; `scripts/reclasificar-simulados.py` (simulacro por defecto) marca como simulados los colectivos antiguos cuyas incidencias son todas simuladas.
- Cuesta una lectura más por zona en el barrido de 5 minutos (la del universo simulado): despreciable con DynamoDB bajo demanda.
- Cambios de contrato **aditivos** (campos opcionales): `reporte.simulado`, `metrica-antena.simulada`, `antena-estado.simulada`, `evento-historial.simulado`, `incidente-colectivo.{simulado,estadoAntesDeAtencion}`, `estado-red.simulacion`, `analitica.{datos,kpis.requierenAtencion}`.
