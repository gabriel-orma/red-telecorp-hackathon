# E3: Detección colectiva + Step Functions + notificaciones

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 02:00
- **Issue / PR**: #21 (contrato #20)
- **Rama**: feat/21-e3-colectivos

## Qué se hizo
- **Stack `workflows`** (nuevo):
  - **detector** sobre dos DynamoDB Streams (INSERT de incidencias; antenas filtradas a CAIDA/INHABILITADA), con DLQ `onFailure`;
  - **Step Function `incidente-colectivo`**: Map de avisos ×3, verificación de la infraestructura, priorización, resumen (Catch), confirmación, Choice ¿crítico? → SNS directo, Wait + re-verificación, restablecimiento automático o manual, cierre. Retry con backoff en todos los Task.
- **Candado por zona** (clave condicional `COLECTIVO#zona` en `dedup`): un solo colectivo abierto por zona; lo que llega después se suma.
- **Re-priorización** en cada re-verificación; si escala a CRÍTICA, alerta al NOC por SNS.
- **Notificaciones**: aviso en la app (historial `NOTIFICACION_ENVIADA`) + email por SNS con FilterPolicy por usuario (opt-in en el portal).
- **Base**: tópicos `avisos` y `alertas-operador`, SSM `/telecorp/<stage>/reglas`, DLQ del detector. Reglas nuevas con pruebas (20 en total).
- **API**: `GET /api/colectivos`, `GET /api/colectivos/{id}`, `POST /api/colectivos/{id}/restablecer`; el detalle de una incidencia incluye su colectivo.
- **Frontend**:
  - pestaña **Colectivos** (lista, detalle, **diagrama del flujo** con el paso en curso, enlace a la ejecución en la consola);
  - **banner + sonido** al detectarse uno nuevo;
  - **zonas que laten** en el mapa (a cualquier zoom);
  - tarjeta de colectivos activos en el panel lateral;
  - avisos como mensajes en el seguimiento del usuario.

## Pruebas E2E en el lab
| Prueba | Resultado |
|---|---|
| 9 reportes en ZONA-05 | Sin colectivo ✅ |
| 13 reportes | Colectivo, EN_EVALUACION → CONFIRMADA, ALTA (65), 26 avisos ✅ |
| ANT-013 = 0 | Origen AMBOS, re-priorizado a CRÍTICA (115) en <10 s ✅ |
| ANT-013 restaurada | RESTABLECIDO → CERRADO automático, 39 avisos, 6.4 min, ejecución SUCCEEDED ✅ |
| ANT-019 = 0 sin reportes | Colectivo proactivo (METRICAS_ANTENA, ALTA) ✅ |
| Operador "restablecido" | Cierre en la siguiente verificación ✅ |

## Pendiente / siguiente paso
- D7 (fórmula de prioridad): hoy es provisional y está en SSM.
- E4 (segunda nube + IA): reemplazar la plantilla del paso `Resumir`.

## Notas para los otros agentes
- Handlers en `src/`: Lambda importa `src/<modulo>`; para imports hermanos se agrega la carpeta al `sys.path` (ver `detector.py`).
- Los streams con `maximumRetryAttempts` **descartan** el lote tras los reintentos: siempre configura `destinations.onFailure`.
- Las ejecuciones en curso usan la definición con la que arrancaron, pero las Lambdas toman el código nuevo: un parámetro nuevo debe tener un valor por defecto.
- Para disparar un colectivo: `python scripts/demo/reportar.py <URL> --zona ZONA-05 --n 12`.
