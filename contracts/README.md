# Contratos compartidos — v0 (BORRADOR)

Definen la forma de los datos que cruzan entre módulos. **Programa contra estos contratos, no contra la implementación de otra persona.** Para cambiarlos, abre un issue `contrato` (ver `AGENTS.md` §4).

> v0 es un **borrador** para arrancar. Mientras nadie haya construido encima, ajustarlo es barato: hazlo ya mismo vía issue.

| Contrato | Archivo | Productor → Consumidor |
|---|---|---|
| Reporte de usuario (entrada del portal) | [`schemas/reporte.schema.json`](schemas/reporte.schema.json) | Portal → API |
| Incidencia (estado y gestión) | [`schemas/incidencia.schema.json`](schemas/incidencia.schema.json) | API ↔ panel, detector, workflows |
| Evento de historial | [`schemas/evento-historial.schema.json`](schemas/evento-historial.schema.json) | Cualquier cambio de estado → historial, analítica |
| Métrica de antena | [`schemas/metrica-antena.schema.json`](schemas/metrica-antena.schema.json) | Simulador → clasificador |
| Estado actual de antena | [`schemas/antena-estado.schema.json`](schemas/antena-estado.schema.json) | Clasificador → detector, correlación, API |
| Incidente colectivo | [`schemas/incidente-colectivo.schema.json`](schemas/incidente-colectivo.schema.json) | Detector → Step Functions → notificaciones, analítica |
| Catálogo de zonas y antenas | [`zonas.json`](zonas.json) | Referencia para todos |

Hay ejemplos válidos en [`ejemplos/`](ejemplos/). Úsalos como mocks y en las pruebas.

## Convenciones
- Fechas en **ISO 8601 UTC** (`2026-11-13T23:10:00Z`).
- IDs como texto: `INC-<ulid>`, `COL-<ulid>`, `ANT-<n>`, `ZONA-<n>`.
- Enums en `MAYUSCULAS_CON_GUION_BAJO`.
- Nombres de campos en `camelCase` y en español.
