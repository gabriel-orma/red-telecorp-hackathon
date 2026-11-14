# D8: DynamoDB con tablas separadas

- Estado: aceptada (el diseño de claves está en borrador: se ajusta vía issue `contrato` o `decision` antes de construir encima)
- Issue: #1

## Decisión
Una tabla por entidad, en modo **on-demand** (`PAY_PER_REQUEST`) y con **Point-in-Time Recovery** activado (suma en la rúbrica de persistencia y alta disponibilidad).

## Tablas (propuesta de claves)

| Tabla | PK | SK | Índices / Streams | Contrato |
|---|---|---|---|---|
| `telecorp-<stage>-incidencias` | `incidenciaId` | — | GSI `zona-fecha`: PK `zonaId`, SK `creadaEn` (para contar usuarios distintos por zona en 24 h) · **Stream** activado (para el detector) | `incidencia.schema.json` |
| `telecorp-<stage>-historial` | `entidadId` | `sk` = `ocurridoEn#tipoEvento#aleatorio` | — | `evento-historial.schema.json` |
| `telecorp-<stage>-metricas` | `antenaId` | `medidoEn` | **TTL** (`expiraEn`, 7 días) | `metrica-antena.schema.json` |
| `telecorp-<stage>-antenas` | `antenaId` | — | **Stream** activado (detección proactiva por cambio de estado) | `antena-estado.schema.json` |
| `telecorp-<stage>-colectivos` | `incidenteColectivoId` | — | GSI `zona-estado`: PK `zonaId`, SK `estado` (evitar duplicar un colectivo abierto en la misma zona) | `incidente-colectivo.schema.json` |

## Consecuencias
- Cada tabla la crea **un solo** `serverless.yml` y la exporta como `Output` (ver [2026-11-13-serverless-framework](2026-11-13-serverless-framework.md)).
- Los nombres de tabla llegan a las Lambdas por **variables de entorno**, nunca escritos a mano en el código.

## Enmienda (E1, 2026-11-14, issue #11)
- Nueva tabla **`antenas`** (estado actual, con Stream). La detección proactiva escucha *cambios de estado* en vez de cada métrica: menos invocaciones y lógica más simple.
- `metricas` **pierde el GSI y el Stream**: la correlación usa el estado actual de `antenas`, y la serie solo se consulta por antena (gráfico del detalle).
- La SK de `historial` lleva un sufijo aleatorio para que dos eventos en el mismo milisegundo no choquen.
- `colectivos` es el nombre corto definitivo de la tabla de incidentes colectivos.

## Enmienda (E2, 2026-11-14, issue #15)
- Nueva tabla **`dedup`** (PK `clave` = `usuarioId#zonaId`, TTL `expiraEn`). La deduplicación se hace con un **put condicional** al recibir el reporte: es atómica e inmediata. Consultar el GSI `zona-fecha` no servía, porque es eventualmente consistente y el worker de SQS aún no había escrito. La clave se libera cuando la incidencia se resuelve o se cierra.
