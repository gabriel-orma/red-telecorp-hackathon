# D10: Contadores agregados para el estado público (estilo Downdetector)

- Estado: aceptada
- Issue: #25

## Contexto
La página pública muestra los reportes de las últimas 24 h contra "lo normal", los tipos más reportados y las zonas. Calcularlo escaneando la tabla de incidencias no escala con millones de usuarios.

## Decisión
- Tabla **`estadisticas`**: PK `serie` (`GLOBAL` o `ZONA-xx`), SK `bucket` (inicio de cada bloque de **15 min**). Atributos `total` y `t_<TIPO>`. TTL de 35 días y PITR.
- El worker de reportes hace un **`ADD` atómico** en las series `GLOBAL` y la de la zona apenas registra la incidencia. No hay lectura previa ni contención.
- **Línea base** = promedio del mismo bloque horario en los 7 días previos.
- **Semáforo**:
  - `PROBLEMAS`: hay un incidente colectivo activo;
  - `POSIBLES_PROBLEMAS`: la última hora tiene ≥5 reportes y más de 3× lo normal;
  - si no, `SIN_PROBLEMAS`.
- `GET /api/estado` es público, con 10 s de caché en la Lambda y `Cache-Control` en la respuesta.

## Consecuencias
- Leer 24 h son 96 ítems por serie, sin importar el volumen de reportes: costo y latencia constantes.
- `scripts/demo/historico.py` siembra 8 días de contadores de demo (marcados con `demo`) para que la línea base tenga forma. **Ejecutarlo una sola vez por stage.**
