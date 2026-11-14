# D11: Sistema de diseño neumórfico oscuro

- Estado: aceptada (el equipo eligió el estilo a partir de una referencia y aprobó el mapa antes de extenderlo)
- Issue: #28

## Contexto
El diseño anterior (gris azulado con acento cian, todo hecho a mano) se veía "generado por IA". El equipo pidió un estilo moderno a partir de una referencia de UI neumórfica.

## Decisión
- **Tema `.tema-neu`** (`frontend/src/index.css`):
  - fondo `#16161a`, paneles `#1c1c21` con relieve suave (doble sombra) y campos hundidos (sombra interior);
  - **un único acento**: degradado violeta→rosa (`#7c5cff → #e05ab0`);
  - estados saturados: turquesa normal, ámbar saturada, coral caída, gris inhabilitada;
  - tipografía **Plus Jakarta Sans**;
  - etiquetas en minúsculas normales, sin MAYÚSCULAS espaciadas.
- **Librerías especialistas** (skill `pick-ui-library`, `.claude/skills/`):
  - **Sonner** para las alertas de incidente;
  - **NumberFlow** para las cifras;
  - **cmdk** para la paleta Ctrl+K;
  - se mantienen motion y recharts.
- **Shell del operador**: barra lateral de íconos (barra inferior en el celular) y barra superior con estado en vivo, hora de Lima y buscador.
- El incidente colectivo se muestra en **4 etapas** (Detectado → Verificado y priorizado → Monitoreando → Restablecido); el detalle completo de los 12 pasos sigue en la página de colectivos.
- Regla: **un solo momento llamativo por pantalla** (el mapa en el centro de control; el semáforo en el portal).

## Consecuencias
- Clases utilitarias del tema: `neu`, `neu-chico`, `neu-hundido`, `boton-neu`, `degradado`, `texto-degradado`.
- Los colores de estado son la única fuente en `lib/estados.ts` (y `components/neu/paleta.ts` para el mapa).
- El neumorfismo tiene poco contraste: los colores de estado se mantienen saturados para que las fallas se lean de un vistazo.
