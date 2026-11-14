# Mapa de dolores del cliente → solución

La rúbrica premia resolver **la mayor cantidad de dolores**. Actualiza la columna **Estado** (`⬜ pendiente`, `🟨 en progreso #issue`, `✅ cubierto #PR`) cuando avances.

| # | Dolor | Solución propuesta | Estado |
|---|---|---|---|
| 1 | Clasificar el tráfico de las antenas | Simulador → SQS → Lambda clasificador → DynamoDB | ⬜ |
| 2 | Portal para registrar incidencias | Frontend + API Gateway + Lambda | ⬜ |
| 3 | Estados e historial de las incidencias | DynamoDB: incidencia + eventos de historial | ⬜ |
| 4 | Detectar un incidente colectivo (≥10 usuarios / zona / <24 h) | DynamoDB Streams → Lambda detector → Step Functions | ⬜ |
| 5 | Notificar a los afectados según el estado | SNS (SMS) y SES (email) desde Step Functions | ⬜ |
| 6 | Priorizar por afectados y tipo de zona | Puntaje en Step Functions con `contracts/zonas.json` | ⬜ |
| 7 | Analítica: zonas, antenas y tipos más frecuentes | Exportación a BigQuery + Looker Studio | ⬜ |
| 8 | Antenas con incidentes recurrentes | Step Function diaria de recurrencia → `ESTRUCTURAL` | ⬜ |
| 9 | Detectar antes que el usuario | Antena caída → incidente proactivo + correlación con reportes | ⬜ |
| 10 | Picos masivos sin perder registros | SQS + DLQ + escalado de Lambda; prueba de carga | ⬜ |
| 11 | Histórico (duración, zonas, afectados) | Marcas de tiempo + BigQuery | ⬜ |
| 12 | Costo mínimo y sin infraestructura encendida | 100 % pago por uso | ⬜ |
| 13 | Seguridad de las variables globales | Secrets Manager / SSM | ⬜ |
| 14 | IA aplicada | Gemini: clasificar el texto libre y resumir incidentes | ⬜ |
