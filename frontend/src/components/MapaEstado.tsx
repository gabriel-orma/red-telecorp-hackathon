import { useEffect, useRef } from "react";
import type { GeoJSONSource, Map as MapaML } from "maplibre-gl";
import type { EstadoRed } from "../lib/api";
import { NIVEL_RED } from "../lib/estados";
import { CENTRO_LIMA, ESTILO_OSCURO, circulo, maplibregl } from "../lib/mapa";

/** Mapa compacto del portal: zonas coloreadas por nivel y con brillo según los reportes de 24 h. */
export function MapaEstado({ zonas, seleccion, onZona }: { zonas: EstadoRed["zonas"]; seleccion?: string; onZona: (id: string) => void }) {
  const div = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaML | null>(null);
  const cb = useRef(onZona);
  cb.current = onZona;
  const pendiente = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!div.current) return;
    const m = new maplibregl.Map({
      container: div.current, style: ESTILO_OSCURO, center: CENTRO_LIMA, zoom: 10.3,
      attributionControl: { compact: true }, dragRotate: false, cooperativeGestures: true,
    });
    mapa.current = m;
    m.on("load", () => {
      m.addSource("zonas", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "zonas", type: "fill", source: "zonas", paint: { "fill-color": ["get", "color"], "fill-opacity": ["get", "opacidad"] } });
      m.addLayer({ id: "zonas-borde", type: "line", source: "zonas",
        paint: { "line-color": ["get", "color"], "line-width": ["case", ["get", "sel"], 2.5, 1], "line-opacity": ["case", ["get", "sel"], 1, 0.5] } });
      m.on("click", "zonas", (e) => { const id = e.features?.[0]?.properties?.zonaId; if (id) cb.current(id); });
      m.on("mouseenter", "zonas", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "zonas", () => (m.getCanvas().style.cursor = ""));
      pendiente.current?.();
    });
    return () => m.remove();
  }, []);

  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    const maximo = Math.max(1, ...zonas.map((z) => z.total24h));
    const aplicar = () => (m.getSource("zonas") as GeoJSONSource | undefined)?.setData({
      type: "FeatureCollection",
      features: zonas.map((z) => ({
        type: "Feature", geometry: { type: "Polygon", coordinates: [circulo(z.centro.lng, z.centro.lat, z.radioM)] },
        properties: { zonaId: z.zonaId, sel: z.zonaId === seleccion, color: NIVEL_RED[z.nivel].color,
                      opacidad: 0.08 + 0.42 * (z.total24h / maximo) },
      })),
    });
    if (m.getSource("zonas")) aplicar(); else pendiente.current = aplicar;
  }, [zonas, seleccion]);

  return <div ref={div} className="h-64 w-full overflow-hidden rounded-xl border border-borde" />;
}
