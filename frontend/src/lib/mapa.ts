// Configuración común de MapLibre (mapa del operador y selector del portal).
import * as maplibregl from "maplibre-gl";
// maplibre v6 carga su web worker como módulo aparte: Vite lo emite como asset y le pasamos la URL.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";

maplibregl.setWorkerUrl(workerUrl);

export { maplibregl };
export const ESTILO_OSCURO = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
export const CENTRO_LIMA: [number, number] = [-77.03, -12.075];

/** Polígono circular aproximado (área de cobertura de una zona). */
export function circulo(lng: number, lat: number, radioM: number, puntos = 72): [number, number][] {
  const coords: [number, number][] = [];
  for (let i = 0; i <= puntos; i++) {
    const a = (i / puntos) * 2 * Math.PI;
    const dx = (radioM * Math.cos(a)) / (111320 * Math.cos((lat * Math.PI) / 180));
    const dy = (radioM * Math.sin(a)) / 111320;
    coords.push([lng + dx, lat + dy]);
  }
  return coords;
}
