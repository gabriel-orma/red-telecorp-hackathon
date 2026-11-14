# Diseño del mapa según el zoom

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 01:30
- **Issue / PR**: #18
- **Rama**: feat/18-mapa-zoom

## Qué se hizo
Feedback de diseño ("de lejos los puntos se ven raros"):
- **Antenas**: aparecen desde zoom 11 con un fundido hasta 11.8 (`minzoom` + opacidad interpolada). Por debajo de 11 no se dibujan ni se pueden clicar. El pulso respeta el mismo fundido.
- **Nombres de zona**: visibles desde zoom 12, con una transición de 250 ms.
- **Contornos**: línea sólida fina (0.6–1.1 px según el zoom) y colores desaturados. Una zona normal queda casi invisible (borde de opacidad 0.2, relleno de 0.025); solo las zonas con falla (rojo) o saturación (ámbar) destacan de lejos.
- **Mapa de calor**: la opacidad baja de 0.75 a 0.4 al acercarse, para no tapar las antenas.

## Cómo probarlo
Centro de control → alejar con la rueda: solo contornos y calor. Clic en una zona de la lista → acerca y aparecen las antenas y los nombres.

## Notas para los otros agentes
- Para ocultar un marcador HTML de maplibre, cambia la opacidad de un **hijo** del elemento: maplibre controla el `style` del elemento raíz.
- Los umbrales están en las constantes `ZOOM_ANTENAS`, `ZOOM_ANTENAS_PLENO` y `ZOOM_ETIQUETAS` de `MapaRed.tsx`.
