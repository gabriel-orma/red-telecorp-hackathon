import { useEffect, useRef } from "react";
import type { GeoJSONSource, Map as MapaML, MapLayerMouseEvent, MapMouseEvent } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { Antena, EstadoAntena, Incidencia, Zona } from "../lib/api";
import { ESTADO, TIPO_ZONA } from "../lib/estados";
import { CENTRO_LIMA, ESTILO_OSCURO as ESTILO, circulo, maplibregl } from "../lib/mapa";

// Expresión de color por estado (misma paleta que el resto del panel).
const colorPorEstado = [
  "match", ["get", "estado"],
  ...(Object.entries(ESTADO) as [EstadoAntena, { color: string }][]).flatMap(([e, v]) => [e, v.color]),
  ESTADO.SIN_DATOS.color,
] as unknown as maplibregl.ExpressionSpecification;

const geoAntenas = (antenas: Antena[], seleccion: string | null): FeatureCollection => ({
  type: "FeatureCollection",
  features: antenas.map((a) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [a.lng, a.lat] },
    properties: { antenaId: a.antenaId, estado: a.estado, seleccionada: a.antenaId === seleccion },
  })),
});

const geoZonas = (zonas: Zona[]): FeatureCollection => ({
  type: "FeatureCollection",
  features: zonas.map((z) => ({
    type: "Feature",
    geometry: { type: "Polygon", coordinates: [circulo(z.centro.lng, z.centro.lat, z.radioM)] },
    properties: { zonaId: z.zonaId, estado: z.estado },
  })),
});

/** Puntos del mapa de calor: ubicación del reporte o, si no la dio, un punto estable dentro de su zona. */
const geoReportes = (reportes: Incidencia[], zonas: Zona[]): FeatureCollection => ({
  type: "FeatureCollection",
  features: reportes.flatMap((r) => {
    let lng = r.reporte.ubicacion?.lng, lat = r.reporte.ubicacion?.lat;
    if (lat === undefined || lng === undefined) {
      const z = zonas.find((x) => x.zonaId === r.zonaId);
      if (!z) return [];
      let h = 0;
      for (const c of r.incidenciaId) h = (h * 31 + c.charCodeAt(0)) >>> 0;
      const ang = (h % 360) * (Math.PI / 180), dist = ((h >> 9) % 100) / 100 * z.radioM * 0.7;
      lat = z.centro.lat + (dist * Math.sin(ang)) / 111320;
      lng = z.centro.lng + (dist * Math.cos(ang)) / (111320 * Math.cos((z.centro.lat * Math.PI) / 180));
    }
    return [{ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [lng, lat] }, properties: {} }];
  }),
});

interface Props {
  antenas: Antena[];
  zonas: Zona[];
  reportes: Incidencia[];
  seleccion: string | null;
  onSeleccionar: (antenaId: string | null) => void;
  enfocarZona: Zona | null;
}

export function MapaRed({ antenas, zonas, reportes, seleccion, onSeleccionar, enfocarZona }: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaML | null>(null);
  const listo = useRef(false);
  const etiquetas = useRef<maplibregl.Marker[]>([]);
  const pendiente = useRef<(() => void) | null>(null);
  const onSel = useRef(onSeleccionar);
  onSel.current = onSeleccionar;

  // Crear el mapa una sola vez.
  useEffect(() => {
    if (!contenedor.current) return;
    const m = new maplibregl.Map({
      container: contenedor.current,
      style: ESTILO,
      center: CENTRO_LIMA,
      zoom: 11.3,
      pitch: 0,
      attributionControl: { compact: true },
    });
    mapa.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

    m.on("load", () => {
      m.addSource("zonas", { type: "geojson", data: geoZonas([]) });
      m.addSource("antenas", { type: "geojson", data: geoAntenas([], null) });
      m.addSource("reportes", { type: "geojson", data: geoReportes([], []) });

      m.addLayer({
        id: "zonas-relleno", type: "fill", source: "zonas",
        paint: {
          "fill-color": colorPorEstado,
          "fill-opacity": ["match", ["get", "estado"], ["CAIDA", "INHABILITADA"], 0.16, "SATURADA", 0.1, 0.05],
        },
      });
      m.addLayer({
        id: "zonas-borde", type: "line", source: "zonas",
        paint: { "line-color": colorPorEstado, "line-opacity": 0.55, "line-width": 1.2, "line-dasharray": [2, 2] },
      });
      m.addLayer({
        id: "reportes-calor", type: "heatmap", source: "reportes",
        paint: {
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 10, 18, 14, 45],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 10, 0.8, 14, 1.6],
          "heatmap-opacity": 0.75,
          "heatmap-color": [
            "interpolate", ["linear"], ["heatmap-density"],
            0, "rgba(0,0,0,0)", 0.2, "rgba(124,58,237,0.45)", 0.45, "#db2777", 0.7, "#f97316", 1, "#fde047",
          ],
        },
      });
      m.addLayer({
        id: "antenas-pulso", type: "circle", source: "antenas",
        filter: ["in", ["get", "estado"], ["literal", ["CAIDA", "INHABILITADA"]]],
        paint: { "circle-color": colorPorEstado, "circle-radius": 10, "circle-opacity": 0.5, "circle-blur": 0.4 },
      });
      m.addLayer({
        id: "antenas-halo", type: "circle", source: "antenas",
        paint: { "circle-color": colorPorEstado, "circle-radius": 13, "circle-opacity": 0.22, "circle-blur": 0.8 },
      });
      m.addLayer({
        id: "antenas-punto", type: "circle", source: "antenas",
        paint: {
          "circle-color": colorPorEstado,
          "circle-radius": ["case", ["get", "seleccionada"], 8, 5.5],
          "circle-stroke-color": ["case", ["get", "seleccionada"], "#ffffff", "#060912"],
          "circle-stroke-width": ["case", ["get", "seleccionada"], 2.5, 1.5],
        },
      });

      m.on("click", "antenas-punto", (e: MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.antenaId as string | undefined;
        if (id) onSel.current(id);
      });
      m.on("click", (e: MapMouseEvent) => {
        if (!m.queryRenderedFeatures(e.point, { layers: ["antenas-punto"] }).length) onSel.current(null);
      });
      m.on("mouseenter", "antenas-punto", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "antenas-punto", () => (m.getCanvas().style.cursor = ""));

      // Pulso de las antenas en falla: radio y opacidad animados.
      let frame = 0;
      const animar = (t: number) => {
        const fase = (t % 1600) / 1600;
        if (m.getLayer("antenas-pulso")) {
          m.setPaintProperty("antenas-pulso", "circle-radius", 8 + fase * 26);
          m.setPaintProperty("antenas-pulso", "circle-opacity", 0.55 * (1 - fase));
        }
        frame = requestAnimationFrame(animar);
      };
      frame = requestAnimationFrame(animar);
      m.once("remove", () => cancelAnimationFrame(frame));

      listo.current = true;
      pendiente.current?.();
    });

    return () => {
      listo.current = false;
      m.remove();
    };
  }, []);

  // Actualizar datos en cada polling.
  useEffect(() => {
    const m = mapa.current;
    if (!m) return;
    const aplicar = () => {
      (m.getSource("antenas") as GeoJSONSource | undefined)?.setData(geoAntenas(antenas, seleccion));
      (m.getSource("zonas") as GeoJSONSource | undefined)?.setData(geoZonas(zonas));
      (m.getSource("reportes") as GeoJSONSource | undefined)?.setData(geoReportes(reportes, zonas));
    };
    if (listo.current) aplicar();
    else pendiente.current = aplicar;
  }, [antenas, zonas, reportes, seleccion]);

  // Etiquetas HTML de zona (nombre + tipo), recreadas solo si cambia el catálogo.
  const claveZonas = zonas.map((z) => z.zonaId).join();
  useEffect(() => {
    const m = mapa.current;
    if (!m || !zonas.length) return;
    // Encuadre inicial: todas las zonas visibles.
    const limites = new maplibregl.LngLatBounds();
    zonas.forEach((z) => {
      const dLat = z.radioM / 111320;
      const dLng = z.radioM / (111320 * Math.cos((z.centro.lat * Math.PI) / 180));
      limites.extend([z.centro.lng - dLng, z.centro.lat - dLat]);
      limites.extend([z.centro.lng + dLng, z.centro.lat + dLat]);
    });
    m.fitBounds(limites, { padding: { top: 80, bottom: 60, left: 30, right: 30 }, duration: 0, maxZoom: 13 });
    etiquetas.current.forEach((e) => e.remove());
    etiquetas.current = zonas.map((z) => {
      const el = document.createElement("div");
      el.className = "pointer-events-none select-none text-center";
      el.innerHTML = `<div style="font:600 11px var(--font-sans);color:#cbd5e1;text-shadow:0 1px 6px #000,0 0 2px #000;letter-spacing:.02em">${z.nombre}</div>
        <div style="font:500 9px var(--font-mono);color:#64748b;text-transform:uppercase;letter-spacing:.08em">${TIPO_ZONA[z.tipo].etiqueta}</div>`;
      const lat = z.centro.lat - (z.radioM * 0.75) / 111320;
      return new maplibregl.Marker({ element: el }).setLngLat([z.centro.lng, lat]).addTo(m);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [claveZonas]);

  useEffect(() => {
    if (enfocarZona && mapa.current) {
      mapa.current.flyTo({ center: [enfocarZona.centro.lng, enfocarZona.centro.lat], zoom: 14, speed: 1.4 });
    }
  }, [enfocarZona]);

  // maplibre pone `position: relative` en su contenedor; por eso el posicionamiento va en un div externo.
  return (
    <div className="absolute inset-0">
      <div ref={contenedor} className="h-full w-full" />
    </div>
  );
}
