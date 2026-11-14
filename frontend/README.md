# Frontend: Centro de Control (D5)

React + Vite + TypeScript + Tailwind v4 + MapLibre GL + Framer Motion. Modo oscuro. **Sin lógica de negocio**: todo sale de `/api`.

```
src/
  App.tsx                 layout + polling (3 s)
  lib/api.ts              cliente y tipos (siguen contracts/)
  lib/estados.ts          colores y etiquetas por estado/tipo de zona
  components/MapaRed.tsx  mapa: zonas (cobertura), antenas (color + pulso en falla)
  components/PanelLateral.tsx    KPIs + zonas ordenadas por gravedad
  components/DetalleAntena.tsx   detalle, gráfico de 30 min y "simular falla"
  components/PanelSimulador.tsx  encender/apagar el simulador
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
