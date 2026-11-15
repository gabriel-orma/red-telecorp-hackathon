# E7.5: Línea de tiempo tipo editor de video + simulación acelerada

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 13:00
- **Issue / PR**: #38
- **Rama**: feat/38-linea-tiempo-acelerada

## Qué se hizo
- **`GET /api/linea-tiempo?horas=`** (`services/api/src/linea_tiempo.py`):
  - reportes de la ventana (GSI `zona-fecha`, una consulta por zona);
  - estado inicial y cambios de cada antena (del historial inmutable);
  - vida de cada colectivo que se cruza con la ventana, con sus cambios de estado y de prioridad.
  - Consultas en paralelo (cliente de bajo nivel, seguro entre hilos) y caché de 2 s. Lógica pura probada.
- **Página `/linea-tiempo`** (ícono de película en la barra lateral):
  - editor con regla, cabezal y 3 pistas: incidentes (color por prioridad de cada momento, rombos en cambios de estado), antenas (tramos en falla/saturación) y reportes (onda tipo audio, coloreada hasta el cabezal);
  - el mapa muestra antenas, zonas, incidentes abiertos y un **mapa de calor con memoria** (los reportes recientes pesan más y destellan al llegar);
  - reproducción 1×/10×/60×/300×, ventanas de 15 min, 1 h, 6 h y 24 h, zoom hasta 48×, teclado;
  - **en vivo**: la ventana termina "ahora" y se actualiza con cada aviso del WebSocket.
- **Simulación acelerada** (`ACELERADA` en "Simular escenario"): 60 pasos de 3 s.
  - 4 eventos en zonas lejanas entre sí: caída de antena (detección proactiva), ola de reportes (colectivo por reportes y correlación posterior), corte de energía y tormenta local.
  - Cada evento se recupera solo (se quitan las fallas forzadas) y el colectivo se cierra por la Step Function.
  - Reportes sueltos de fondo en otras zonas (no llegan al umbral).
  - Mientras dura: monitoreo del colectivo cada 4 s (en vez de 30 s) y `factorTiempo` ×60 para la prioridad (escala en segundos).
  - Narrativa del paso actual en el estado del escenario ("Corte de energía en …").
- **UI a prueba de cambios rápidos**: ver `frontend/README.md` (polling de un solo vuelo, throttle con ejecución final, toasts agrupados, animación de posición en la cola, destello en filas nuevas, tope de filas).
- Se corrigió que el filtro por zona de Incidencias no recargaba hasta el siguiente ciclo de polling.

## Cómo probar
1. Abrir `/linea-tiempo` → "Simular escenario" → **Acelerada** → elegir zona → Iniciar.
2. La ventana pasa a 15 min en vivo: se ven aparecer clips de incidentes y antenas y la onda de reportes.
3. Al terminar (~3 min), pulsar ▶ a 10×: el mapa "repite" los 4 eventos.
4. `pytest`: 44 pruebas.

## Estado de la verificación
- Desplegado en `dev-gabriel` (despliegue completo sin errores), pero **no se probó en el navegador**: la cuenta de AWS Academy de ese stage fue bloqueada.
- Pendiente: desplegar en la cuenta nueva (`bash scripts/deploy.sh <stage>`) y probar la simulación acelerada y la línea de tiempo.

## Notas para los otros agentes
- Fuera de "en vivo" la línea de tiempo NO recarga datos a propósito (si no, los clips se moverían bajo el cursor).
- `useAlCambiar(tipos, fn, intervaloMs)` ahora es throttle: no volver a debounce (con avisos continuos no dispararía nunca).
