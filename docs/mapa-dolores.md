# Mapa de dolores del cliente → solución

La rúbrica premia resolver **la mayor cantidad de dolores**. Actualiza la columna **Estado** (`⬜ pendiente`, `🟨 en progreso #issue`, `✅ cubierto #PR`) cuando avances.

| # | Dolor | Solución propuesta | Estado |
|---|---|---|---|
| 1 | Clasificar el tráfico de las antenas | Simulador → SQS → Lambda clasificador → DynamoDB | ✅ E1 (#11) |
| 2 | Portal para registrar incidencias | Frontend + API Gateway + Lambda | ✅ E2 (#15) + E3.5 (#25): cuenta Cognito, solo tipo + descripción, ubicación automática |
| 3 | Estados e historial de las incidencias | DynamoDB: incidencia + eventos de historial | ✅ E2 (#15): transiciones validadas + historial inmutable |
| 4 | Detectar un incidente colectivo (≥10 usuarios / zona / <24 h) | DynamoDB Streams → Lambda detector → Step Functions | ✅ E3 (#21) |
| 5 | Notificar a los afectados según el estado | Map de Step Functions → aviso en la app + email SNS (opt-in); SES/SMS bloqueados en el lab | ✅ E3 (#21) |
| 6 | Priorizar por afectados y tipo de zona | Puntaje en Step Functions con `contracts/zonas.json` | 🟨 E3: fórmula provisional en SSM (D7) + re-priorización; lista ordenada en E6 |
| 7 | Analítica: zonas, antenas y tipos más frecuentes | Contadores agregados + estado público; histórico en la 2.ª nube | 🟨 E3.5: estado público (24 h vs base, tipos, zonas); analítica del operador en E6 |
| 8 | Antenas con incidentes recurrentes | Step Function diaria de recurrencia → `ESTRUCTURAL` | ⬜ |
| 9 | Detectar antes que el usuario | Antena caída → incidente proactivo + correlación con reportes | 🟨 E3: detección proactiva + correlación (origen AMBOS); la métrica "X min antes" va en E6 |
| 10 | Picos masivos sin perder registros | SQS + DLQ + escalado de Lambda; prueba de carga | ✅ E5 (#30): 480 reportes en 5,5 s, 0 perdidos, DLQ vacía (`scripts/demo/carga.py`) |
| 11 | Histórico (duración, zonas, afectados) | Marcas de tiempo + BigQuery | ⬜ |
| 12 | Costo mínimo y sin infraestructura encendida | 100 % pago por uso | 🟨 E1: todo on-demand; simulador apagado por defecto |
| 13 | Seguridad de las variables globales | Secrets Manager / SSM | 🟨 E1: SSM (config) + Secrets Manager (key de IA) |
| 14 | IA aplicada | Gemini: clasificar el texto libre y resumir incidentes | ⬜ |
