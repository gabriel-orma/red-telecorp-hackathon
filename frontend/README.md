# Frontend: Centro de Control (D5)

React + Vite + TypeScript + Tailwind v4 + MapLibre GL + Framer Motion + Sonner + NumberFlow + cmdk. Tema neumórfico oscuro (D11): clases `neu`, `neu-hundido`, `boton-neu`, `degradado` en `src/index.css`. **Sin lógica de negocio**: todo sale de `/api`.

Rutas (router mínimo en `lib/router.ts`; la Lambda `web` devuelve `index.html` para cualquier ruta):

| Ruta | Pantalla |
|---|---|
| `/` | Centro de control: mapa en vivo, KPIs, simulador, mapa de calor, incidente activo (`?zona=`, `?antena=` para enfocar) |
| `/colectivos` | Incidentes colectivos y el flujo de Step Functions (con la tarjeta "detectado X min antes") |
| `/analitica` | Analítica operativa: KPIs, zonas, antenas, tipos, duración y recurrencia |
| `/incidencias` | Panel del operador: lista filtrable, detalle, cambio de estado e historial |
| `/portal` | **Estado público** estilo Downdetector: semáforo, gráfico de 24 h vs lo normal, tipos, zonas, mapa e incidentes |
| `/portal/cuenta` | Ingresar / crear cuenta (Cognito) · perfil · mis reportes |
| `/portal/reportar` | Reporte mínimo (requiere sesión): tipo + descripción; ubicación automática |
| `/portal/seguimiento/{id}` | Seguimiento tipo "pedido en camino" + estado de la zona |

```
src/
  App.tsx                      rutas, polling, shell del operador, alertas (Sonner) y Ctrl+K
  pages/MapaNeu.tsx            centro de control (mapa en vivo)
  pages/                       PanelIncidencias, Colectivos, EstadoPublico, Cuenta, Reportar, Seguimiento
  components/neu/              ShellNeu, PaletaComandos (cmdk), Piezas (Cifra, Anillo, Interruptor, PasosColectivo),
                               DetalleAntenaNeu, alertas, paleta (colores del mapa y etapas del flujo)
  components/MapaRed.tsx       mapa MapLibre (zonas, antenas, calor, colectivos que laten); prop `paleta`
  components/LineaTiempo.tsx   progreso de estados + historial
  lib/api.ts · lib/auth.ts     cliente del API (tipos de contracts/) y Cognito
  lib/estados.ts               colores y etiquetas (fuente única)
```

## Desarrollo local contra el API desplegado
```bash
cd frontend
npm install
VITE_API_PROXY=https://<id>.execute-api.us-east-1.amazonaws.com npm run dev
```

## Publicar
`bash scripts/deploy.sh <stage> frontend` compila y sube `dist/` al bucket. La Lambda `web` lo sirve por HTTPS.

Mapa base: CARTO Dark Matter (gratuito, sin API key, con atribución).

## Tiempo real y experiencia (E7)
- `lib/tiempoReal.ts`: **una** conexión WebSocket compartida (URL en `/api/config`), reconexión con espera creciente y ping cada 4 min.
  - Con WebSocket, el polling baja a 30 s (respaldo) y los datos se refrescan al llegar cada aviso.
  - Sin WebSocket, vuelve el polling de 3 s.
  - La barra superior muestra "En vivo · WebSocket" o "En vivo · polling".
- **Reproducción del historial** (`components/neu/Reproduccion.tsx`): deslizador y play de 12 s sobre el historial inmutable del incidente (estado, reportes acumulados, antenas, prioridad).
- **Reporte por voz** (`components/Dictado.tsx`): Web Speech API (`es-PE`); si el navegador no la soporta, el botón no aparece.
- **Mapa 3D**: botón "3D" en la leyenda; las zonas se extruyen según los reportes de 24 h y la cámara se inclina.
- **Modo sala** (pantalla completa, sin barra lateral ni listas largas) y **alto contraste**: botones en la barra superior, guardados en el navegador.

## Línea de tiempo y simulación acelerada (E7.5)
- `pages/LineaTiempoNeu.tsx` (`/linea-tiempo`): mapa ("monitor") + "En este instante" + editor.
- `components/neu/EditorTiempo.tsx`: barra de transporte (play, en vivo, velocidad, ventana, zoom), regla, pistas y cabezal.
  - Las pistas están memorizadas; en cada cuadro solo se mueve el cabezal y la parte "reproducida" de la onda.
  - Teclado: espacio reproduce, ← → mueven el cabezal (Shift: ×10), Inicio/Fin.
- `lib/lineaTiempo.ts`: indexa los datos una vez y responde "¿cómo estaba la red en t?" con búsqueda binaria.
- Fuera de "en vivo" los datos se **congelan** (los clips no se mueven bajo el cursor); al llegar al final de la reproducción vuelve a "en vivo".
- Robustez ante cambios rápidos:
  - `usePolling`: un solo pedido en vuelo; los avisos que llegan mientras tanto agendan UNA recarga más.
  - `useAlCambiar`: throttle con ejecución final garantizada (un debounce nunca dispararía con avisos continuos).
  - Toasts: máximo 3 visibles y agrupados si llegan más de 2 incidentes a la vez.
  - Cola de atención con animación de posición; incidencias con destello en filas nuevas o que cambian de estado y tope de 250 filas.

## Inicio (dashboard) y navegación
- `/` es ahora **Inicio** (`pages/Inicio.tsx`): estado general de la red, indicadores (incidentes, antenas en falla, reportes 24 h, clientes en zonas con falla), gráfico de reportes contra lo normal, cola de atención, zonas por gravedad y accesos a todas las pantallas. Si hay una simulación en curso, lo avisa con enlace a la línea de tiempo.
- El mapa en vivo pasó a `/mapa` (la paleta Ctrl+K y la analítica ya enlazan ahí: `/mapa?zona=` y `/mapa?antena=`).
- El portal (estado público, reportar, cuenta, seguimiento) tiene un botón **Inicio** para volver al panel; en celular la barra del portal muestra solo íconos.
- El logotipo "TC" de la barra lateral también lleva al inicio.
