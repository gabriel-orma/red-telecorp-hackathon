# E6: Inteligencia operativa

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 11:10
- **Issue / PR**: #33 (contrato #32 / PR #34)
- **Rama**: feat/33-e6-inteligencia

## Qué se hizo
- **Correlación**: `deteccionAnticipadaMin` = primer reporte − primera falla de antena.
  - Sello en el banner del mapa ("Detectado 10 min antes que el primer reporte") y tarjeta grande en el detalle del colectivo.
  - Si los usuarios fueron primero, se dice ("Los usuarios avisaron X min antes").
- **Prioridad con tiempo activo** (TODO D7, en SSM):
  - `(afectados + 10 × antenas en falla) × criticidad × (1 + 0,25 × horas activo)`;
  - se recalcula en cada vuelta del monitoreo, con historial solo si cambia el nivel;
  - **cola de atención** en el mapa, ordenada por puntaje.
- **Step Function `recurrencia`** (diaria, 06:00 de Lima, y a pedido):
  - antenas con 3+ fallas en 7 días → `estructural`, historial y alerta SNS al NOC;
  - se desmarcan al bajar del umbral;
  - aviso en el detalle de la antena.
- **Analítica** (`/analitica`, `GET /api/analitica?dias=`):
  - KPIs (incidentes, afectados, duración promedio, detectados primero por la red con mediana);
  - zonas (escalas independientes para incidentes y reportes), duración y alcance por incidente (escala raíz cuadrada), tipos, antenas con más fallas y botón "Analizar ahora".
- 3 pruebas nuevas ( en total).

## Resultados en el lab
- Recurrencia manual: SUCCEEDED, 36 antenas evaluadas, **ANT-013/014/015 (Hospital Rebagliati) marcadas estructurales** (6, 4 y 4 fallas por las pruebas anteriores).
- Analítica de 7 días: 24 incidentes, 573 afectados, duración promedio de 23 min, 8 detectados primero por la red.
- Tormenta en San Isidro: cola Almenara (CRÍTICA 170) > Rebagliati (CRÍTICA 120) > San Isidro (ALTA 54) > Miraflores (MEDIA 23); sello de detección anticipada en el banner.

## Pendiente / siguiente paso
- **D7**: el equipo debe validar la fórmula de prioridad y el umbral de recurrencia (se cambian en SSM, sin desplegar código).
- E7: tiempo real (WebSocket), reproducción del historial, voz.

## Notas para los otros agentes
- Los datos de `dev-gabriel` mezclan pruebas (carga, tormentas, un incidente que quedó abierto durante un apagado del lab): por eso la analítica usa la mediana y la escala de raíz cuadrada.
- Recharts en barras horizontales con dos magnitudes muy distintas: usa dos `XAxis` con `xAxisId` (uno oculto).
