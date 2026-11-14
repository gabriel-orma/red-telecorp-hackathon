import { useEffect, useRef } from "react";
import type { GeoJSONSource, Map as MapaML, MapLayerMouseEvent, MapMouseEvent } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { Antena, Colectivo, EstadoAntena, Incidencia, Zona } from "../lib/api";
import { ESTADO, PRIORIDAD, TIPO_ZONA } from "../lib/estados";
import { CENTRO_LIMA, ESTILO_OSCURO as ESTILO, circulo, maplibregl } from "../lib/mapa";

export type PaletaMapa = { estados: Record<EstadoAntena, string>; zonas: { CAIDA: string; INHABILITADA: string; SATURADA: string; OTRA: string } };

const PALETA_BASE: PaletaMapa = {
  estados: Object.fromEntries(Object.entries(ESTADO).map(([e, v]) => [e, v.color])) as Record<EstadoAntena, string>,
  // Colores de zona desaturados: el contorno es contexto, no protagonista. Solo las fallas llaman la atención.
  zonas: { CAIDA: "#e07070", INHABILITADA: "#a3acb9", SATURADA: "#d4a65a", OTRA: "#7f93a8" },
};

// Expresiones de color por estado (antenas) y por estado de zona (contornos).
const exprEstados = (p: PaletaMapa) => [
  "match", ["get", "estado"],
  ...Object.entries(p.estados).flatMap(([e, c]) => [e, c]),
  p.estados.SIN_DATOS,
] as unknown as maplibregl.ExpressionSpecification;
const exprZonas = (p: PaletaMapa) => [
  "match", ["get", "estado"],
  "CAIDA", p.zonas.CAIDA, "INHABILITADA", p.zonas.INHABILITADA, "SATURADA", p.zonas.SATURADA,
  p.zonas.OTRA,
] as unknown as maplibregl.ExpressionSpecification;

// Nivel de zoom desde el que aparecen las antenas (con fundido) y los nombres de zona.
const ZOOM_ANTENAS = 11;
const ZOOM_ANTENAS_PLENO = 11.8;
const ZOOM_ETIQUETAS = 12;
const aparecer = (max = 1) =>
  ["interpolate", ["linear"], ["zoom"], ZOOM_ANTENAS, 0, ZOOM_ANTENAS_PLENO, max] as unknown as maplibregl.ExpressionSpecification;

const geoAntenas = (antenas: Antena[], seleccion: string | null): FeatureCollection => ({
  type: "FeatureCollection",
  features: antenas.map((a) => ({
    type: "Feature",
    geometry: { type: "Point", coordinates: [a.lng, a.lat] },
    properties: { antenaId: a.antenaId, estado: a.estado, seleccionada: a.antenaId === seleccion },
  })),
});

const geoZonas = (zonas: Zona[], colectivos: Colectivo[] = []): FeatureCollection => ({
  type: "FeatureCollection",
  features: zonas.map((z) => {
    const c = colectivos.find((x) => x.zonaId === z.zonaId && x.estado !== "CERRADO");
    return {
      type: "Feature",
      geometry: { type: "Polygon", coordinates: [circulo(z.centro.lng, z.centro.lat, z.radioM)] },
      properties: { zonaId: z.zonaId, estado: z.estado, colectivo: !!c, colorColectivo: c ? PRIORIDAD[c.prioridad].color : "#000" },
    };
  }),
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
  colectivos: Colectivo[];
  reportes: Incidencia[];
  seleccion: string | null;
  onSeleccionar: (antenaId: string | null) => void;
  enfocarZona: Zona | null;
  paleta?: PaletaMapa; // opcional: el mapa rediseñado usa su propia paleta
}

export function MapaRed({ antenas, zonas, colectivos, reportes, seleccion, onSeleccionar, enfocarZona, paleta = PALETA_BASE }: Props) {
  const colorPorEstado = exprEstados(paleta);
  const colorZona = exprZonas(paleta);
  const contenedor = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaML | null>(null);
  const listo = useRef(false);
  const etiquetas = useRef<maplibregl.Marker[]>([]);
  const pendiente = useRef<(() => void) | null>(null);
  const onSel = useRef(onSeleccionar);
  onSel.current = onSeleccionar;

  // Nombres de zona solo con zoom suficiente (de lejos se amontonan).
  const actualizarEtiquetas = () => {
    const visibles = (mapa.current?.getZoom() ?? 0) >= ZOOM_ETIQUETAS;
    etiquetas.current.forEach((mk) => {
      const interior = mk.getElement().firstElementChild as HTMLElement | null;
      if (interior) interior.style.opacity = visibles ? "1" : "0";
    });
  };

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
          "fill-color": colorZona,
          "fill-opacity": ["match", ["get", "estado"], ["CAIDA", "INHABILITADA"], 0.14, "SATURADA", 0.06, 0.025],
        },
      });
      m.addLayer({
        id: "zonas-borde", type: "line", source: "zonas",
        paint: {
          "line-color": colorZona,
          "line-opacity": ["match", ["get", "estado"], ["CAIDA", "INHABILITADA"], 0.55, "SATURADA", 0.35, 0.2],
          "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.6, 14, 1.1],
        },
      });
      // Zonas con incidente colectivo abierto: relleno y borde que laten (visibles a cualquier zoom).
      m.addLayer({
        id: "zonas-colectivo-relleno", type: "fill", source: "zonas", filter: ["==", ["get", "colectivo"], true],
        paint: { "fill-color": ["get", "colorColectivo"], "fill-opacity": 0.12 },
      });
      m.addLayer({
        id: "zonas-colectivo-borde", type: "line", source: "zonas", filter: ["==", ["get", "colectivo"], true],
        paint: { "line-color": ["get", "colorColectivo"], "line-width": 2, "line-opacity": 0.9, "line-blur": 1 },
      });
      m.addLayer({
        id: "reportes-calor", type: "heatmap", source: "reportes",
        paint: {
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 10, 18, 14, 45],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 10, 0.8, 14, 1.6],
          "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 11, 0.75, 14, 0.4], // de cerca, que no tape las antenas
          "heatmap-color": [
            "interpolate", ["linear"], ["heatmap-density"],
            0, "rgba(0,0,0,0)", 0.2, "rgba(124,58,237,0.45)", 0.45, "#db2777", 0.7, "#f97316", 1, "#fde047",
          ],
        },
      });
      // Propagación: onda que se expande ~900 m desde cada antena caída (visible a cualquier zoom).
      m.addLayer({
        id: "antenas-onda", type: "circle", source: "antenas",
        filter: ["in", ["get", "estado"], ["literal", ["CAIDA", "INHABILITADA"]]],
        paint: { "circle-color": colorPorEstado, "circle-opacity": 0.06, "circle-stroke-color": colorPorEstado, "circle-stroke-width": 1.5, "circle-radius": 0 },
      });
      m.addLayer({
        id: "antenas-pulso", type: "circle", source: "antenas", minzoom: ZOOM_ANTENAS,
        filter: ["in", ["get", "estado"], ["literal", ["CAIDA", "INHABILITADA"]]],
        paint: { "circle-color": colorPorEstado, "circle-radius": 10, "circle-opacity": 0.5, "circle-blur": 0.4 },
      });
      m.addLayer({
        id: "antenas-halo", type: "circle", source: "antenas", minzoom: ZOOM_ANTENAS,
        paint: { "circle-color": colorPorEstado, "circle-radius": 13, "circle-opacity": aparecer(0.22), "circle-blur": 0.8 },
      });
      m.addLayer({
        id: "antenas-punto", type: "circle", source: "antenas", minzoom: ZOOM_ANTENAS,
        paint: {
          "circle-color": colorPorEstado,
          "circle-opacity": aparecer(),
          "circle-stroke-opacity": aparecer(),
          "circle-radius": ["case", ["get", "seleccionada"], 8, 5.5],
          "circle-stroke-color": ["case", ["get", "seleccionada"], "#ffffff", "#16161a"],
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
        const visible = Math.min(1, Math.max(0, (m.getZoom() - ZOOM_ANTENAS) / (ZOOM_ANTENAS_PLENO - ZOOM_ANTENAS)));
        if (m.getLayer("zonas-colectivo-borde")) {
          const latido = 0.5 + 0.5 * Math.sin((t / 900) * Math.PI);
          m.setPaintProperty("zonas-colectivo-borde", "line-width", 1.5 + latido * 4);
          m.setPaintProperty("zonas-colectivo-borde", "line-opacity", 0.35 + latido * 0.6);
          m.setPaintProperty("zonas-colectivo-relleno", "fill-opacity", 0.06 + latido * 0.14);
        }
        if (m.getLayer("antenas-onda")) {
          const faseOnda = (t % 2800) / 2800;
          const metrosPorPixel = (156543.03 * Math.cos((m.getCenter().lat * Math.PI) / 180)) / 2 ** m.getZoom();
          const suave = 1 - (1 - faseOnda) ** 3; // ease-out: arranca rápido y se frena
          m.setPaintProperty("antenas-onda", "circle-radius", (900 / metrosPorPixel) * suave);
          m.setPaintProperty("antenas-onda", "circle-stroke-opacity", 0.7 * (1 - faseOnda));
          m.setPaintProperty("antenas-onda", "circle-opacity", 0.12 * (1 - faseOnda));
        }
        if (m.getLayer("antenas-pulso")) {
          m.setPaintProperty("antenas-pulso", "circle-radius", 8 + fase * 26);
          m.setPaintProperty("antenas-pulso", "circle-opacity", 0.55 * (1 - fase) * visible);
        }
        frame = requestAnimationFrame(animar);
      };
      frame = requestAnimationFrame(animar);
      m.once("remove", () => cancelAnimationFrame(frame));

      m.on("zoom", actualizarEtiquetas);

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
      (m.getSource("zonas") as GeoJSONSource | undefined)?.setData(geoZonas(zonas, colectivos));
      (m.getSource("reportes") as GeoJSONSource | undefined)?.setData(geoReportes(reportes, zonas));
    };
    if (listo.current) aplicar();
    else pendiente.current = aplicar;
  }, [antenas, zonas, colectivos, reportes, seleccion]);

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
      el.innerHTML = `<div style="transition:opacity 250ms ease;opacity:0">
        <div style="font:600 11px var(--font-sans);color:#cbd5e1;text-shadow:0 1px 6px #000,0 0 2px #000;letter-spacing:.02em">${z.nombre}</div>
        <div style="font:500 9px var(--font-mono);color:#64748b;text-transform:uppercase;letter-spacing:.08em">${TIPO_ZONA[z.tipo].etiqueta}</div>
      </div>`;
      const lat = z.centro.lat - (z.radioM * 0.75) / 111320;
      return new maplibregl.Marker({ element: el }).setLngLat([z.centro.lng, lat]).addTo(m);
    });
    actualizarEtiquetas();
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
