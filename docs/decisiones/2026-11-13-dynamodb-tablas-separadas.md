# D8: DynamoDB con tablas separadas

- Estado: aceptada (el diseño de claves está en borrador: se ajusta vía issue `contrato` o `decision` antes de construir encima)
- Issue: #1

## Decisión
Una tabla por entidad, en modo **on-demand** (`PAY_PER_REQUEST`) y con **Point-in-Time Recovery** activado (suma en la rúbrica de persistencia y alta disponibilidad).

## Tablas (propuesta de claves)

| Tabla | PK | SK | Índices / Streams | Contrato |
|---|---|---|---|---|
| `telecorp-<stage>-incidencias` | `incidenciaId` | — | GSI `zona-fecha`: PK `zonaId`, SK `creadaEn` (para contar usuarios distintos por zona en 24 h) · **Stream** activado (para el detector) | `incidencia.schema.json` |
| `telecorp-<stage>-historial` | `entidadId` | `ocurridoEn#tipoEvento` | — | `evento-historial.schema.json` |
| `telecorp-<stage>-metricas` | `antenaId` | `medidoEn` | GSI `zona-fecha`: PK `zonaId`, SK `medidoEn` · **TTL** para purgar métricas viejas · **Stream** activado (detección proactiva) | `metrica-antena.schema.json` |
| `telecorp-<stage>-incidentes-colectivos` | `incidenteColectivoId` | — | GSI `zona-estado`: PK `zonaId`, SK `estado` (evitar duplicar un colectivo abierto en la misma zona) | `incidente-colectivo.schema.json` |

## Consecuencias
- Cada tabla la crea **un solo** `serverless.yml` y la exporta como `Output` (ver [2026-11-13-serverless-framework](2026-11-13-serverless-framework.md)).
- Los nombres de tabla llegan a las Lambdas por **variables de entorno**, nunca escritos a mano en el código.
