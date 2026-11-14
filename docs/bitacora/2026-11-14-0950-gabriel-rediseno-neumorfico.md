# Rediseño completo de la UI: estilo neumórfico oscuro

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 09:50
- **Issue / PR**: #28
- **Rama**: feat/28-rediseno-neumorfico

## Qué se hizo
- Se instalaron en `.claude/skills/` las 19 skills de diseño de Emil Kowalski (MIT; revisadas: solo Markdown). Ver `.claude/skills/FUENTE.md`.
- Decisión **D11**: tema neumórfico oscuro con acento degradado violeta→rosa.
- **Mapa en vivo** rehecho (`pages/MapaNeu.tsx`, `components/neu/*`):
  - barra lateral; Ctrl+K con cmdk;
  - anillo de antenas operativas y cifras con NumberFlow;
  - detalle de antena flotante;
  - banner del incidente y pasos en 4 etapas;
  - alertas con Sonner.
- **Incidencias, colectivos y portal** con el mismo tema (tokens globales y `.panel` adaptado). Ctrl+K disponible en todas las pantallas del operador: lleva al mapa con `?zona=` o `?antena=`.
- Se borraron los componentes del diseño anterior (CentroControl, Encabezado, PanelLateral, DetalleAntena, PanelSimulador, Leyenda, AlertaColectivo, NumeroAnimado).

## Cómo probarlo
`/`, `/incidencias`, `/colectivos`, `/portal` y `/portal/cuenta`, en escritorio y en celular. Ctrl+K → "ANT-013" → Enter.

## Notas para los otros agentes
- Para elegir una librería nueva, usa `/pick-ui-library`. Para pulir interacciones, `emil-design-eng`.
- Las clases `.neu-hundido` y `.neu` fijan su propio `border-radius`: para un círculo usa `style={{ borderRadius: "50%" }}`.
- La alerta de incidente solo debe sonar con incidentes **nuevos**: hay que esperar a la primera respuesta del API antes de marcar los existentes como vistos.
- Una grilla de una sola columna necesita `grid-cols-[minmax(0,1fr)]`: si no, el contenido largo la ensancha en el celular.
