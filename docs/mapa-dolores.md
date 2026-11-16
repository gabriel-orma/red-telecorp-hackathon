# Mapa de dolores del cliente → solución

La rúbrica premia resolver **la mayor cantidad de dolores**. Actualiza la columna **Estado** (`⬜ pendiente`, `🟨 en progreso #issue`, `✅ cubierto #PR`) cuando avances.

| # | Dolor | Solución propuesta | Estado |
|---|---|---|---|
| 1 | Clasificar el tráfico de las antenas | Simulador → SQS → Lambda clasificador → DynamoDB | ✅ E1 (#11) |
| 2 | Portal para registrar incidencias | Frontend + API Gateway + Lambda | ✅ E2 (#15) + E3.5 (#25): cuenta Cognito, solo tipo + descripción, ubicación automática |
| 3 | Estados e historial de las incidencias | DynamoDB: incidencia + eventos de historial | ✅ E2 (#15): transiciones validadas + historial inmutable |
| 4 | Detectar un incidente colectivo (≥10 usuarios / zona / <24 h) | DynamoDB Streams → Lambda detector → Step Functions | ✅ E3 (#21) |
| 5 | Notificar a los afectados según el estado | Map de Step Functions → aviso en la app + email SNS (opt-in); SES/SMS bloqueados en el lab | ✅ E3 (#21) |
| 6 | Priorizar por afectados y tipo de zona | Puntaje en Step Functions: afectados × criticidad × tiempo activo (+ antenas) | ✅ E6 (#33): cola de atención ordenada; fórmula provisional en SSM (D7) |
| 7 | Analítica: zonas, antenas y tipos más frecuentes | Contadores agregados + estado público; histórico en la 2.ª nube | ✅ E3.5 + E6 (#33): estado público y analítica del operador |
| 8 | Antenas con incidentes recurrentes | Step Function diaria de recurrencia → `ESTRUCTURAL` | ✅ E6 (#33): 3+ fallas en 7 días (provisional, D7), alerta al NOC |
| 9 | Detectar antes que el usuario | Antena caída → incidente proactivo + correlación con reportes | ✅ E3 + E6 (#33): "detectado X min antes que el primer reporte" |
| 10 | Picos masivos sin perder registros | SQS + DLQ + escalado de Lambda; prueba de carga | ✅ E5 (#30): 480 reportes en 5,5 s, 0 perdidos, DLQ vacía (`scripts/demo/carga.py`). Con el tope de D14 el pico se procesa más lento, pero sin pérdidas (86/86 en la verificación del 15-nov) |
| 11 | Histórico (duración, zonas, afectados) | Marcas de tiempo + analítica (2.ª nube en E4) | ✅ E6 (#33): página de analítica (1/7/30 días) |
| 12 | Costo mínimo y sin infraestructura encendida | 100 % pago por uso | ✅ Todo on-demand, simulador apagado por defecto, frontend servido desde S3 sin Lambda (D14) y espejo en el plan gratuito de Cloudflare (D15) |
| 13 | Seguridad de las variables globales | Secrets Manager / SSM | ✅ SSM (configuración) + Secrets Manager (`ia`, `azure`, `cloudflare`); ningún valor en el repo ni en los logs |
| 14 | IA aplicada | ML local para el triage + Gemini opcional para resumir | ✅ D12: modelo propio (TF-IDF + regresión logística) en la Lambda; Gemini opcional con protecciones de costo |
| 15 | Que los clientes sepan del problema aunque la plataforma caiga | Espejo del estado público en una 3.ª nube | ✅ D15 (#48): Cloudflare Workers + KV, respaldo automático de la página pública |
