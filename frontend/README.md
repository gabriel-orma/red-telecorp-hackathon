# Frontend: Centro de Control (D5)

React + Vite + TypeScript + Tailwind v4 + MapLibre GL + Framer Motion + Sonner + NumberFlow + cmdk. Tema neumórfico oscuro (D11): clases `neu`, `neu-hundido`, `boton-neu`, `degradado` en `src/index.css`. **Sin lógica de negocio**: todo sale de `/api`.

Rutas (router mínimo en `lib/router.ts`; la Lambda `web` devuelve `index.html` para cualquier ruta):

| Ruta | Pantalla |
|---|---|
| `/` | Centro de control: mapa en vivo, KPIs, simulador, mapa de calor, incidente activo (`?zona=`, `?antena=` para enfocar) |
| `/colectivos` | Incidentes colectivos y el flujo de Step Functions |
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
