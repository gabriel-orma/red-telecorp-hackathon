import { useEffect, useRef } from "react";
import type { Map as MapaML, MapMouseEvent, Marker } from "maplibre-gl";
import type { Zona } from "../lib/api";
import { CENTRO_LIMA, ESTILO_OSCURO, circulo, maplibregl } from "../lib/mapa";

interface Props {
  zonas: Zona[];
  punto: { lat: number; lng: number } | null;
  onPunto: (p: { lat: number; lng: number }) => void;
}

/** Mapa pequeño para que el usuario marque dónde está (toque o arrastre del pin). */
export function MapaSelector({ zonas, punto, onPunto }: Props) {
  const div = useRef<HTMLDivElement>(null);
  const mapa = useRef<MapaML | null>(null);
  const pin = useRef<Marker | null>(null);
  const cb = useRef(onPunto);
  cb.current = onPunto;

  useEffect(() => {
    if (!div.current) return;
    const m = new maplibregl.Map({
      container: div.current, style: ESTILO_OSCURO, center: CENTRO_LIMA, zoom: 10.6,
      attributionControl: { compact: true }, dragRotate: false,
    });
    mapa.current = m;
    m.on("click", (e: MapMouseEvent) => cb.current({ lat: e.lngLat.lat, lng: e.lngLat.lng }));
    return () => m.remove();
  }, []);

  // Zonas de cobertura como referencia visual.
  useEffect(() => {
    const m = mapa.current;
    if (!m || !zonas.length) return;
    const dibujar = () => {
      const datos = {
        type: "FeatureCollection" as const,
        features: zonas.map((z) => ({
          type: "Feature" as const, properties: {},
          geometry: { type: "Polygon" as const, coordinates: [circulo(z.centro.lng, z.centro.lat, z.radioM)] },
        })),
      };
      if (m.getSource("cobertura")) return;
      m.addSource("cobertura", { type: "geojson", data: datos });
      m.addLayer({ id: "cobertura", type: "fill", source: "cobertura", paint: { "fill-color": "#22d3ee", "fill-opacity": 0.08 } });
      m.addLayer({ id: "cobertura-borde", type: "line", source: "cobertura", paint: { "line-color": "#22d3ee", "line-opacity": 0.35, "line-dasharray": [2, 2] } });
    };
    if (m.isStyleLoaded()) dibujar(); else m.once("load", dibujar);
  }, [zonas]);

  // Pin del usuario.
  useEffect(() => {
    const m = mapa.current;
    if (!m || !punto) return;
    if (!pin.current) {
      const el = document.createElement("div");
      el.innerHTML = `<div style="width:22px;height:22px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:#22d3ee;box-shadow:0 0 0 4px #22d3ee44,0 6px 14px #000a;border:2px solid #fff"></div>`;
      pin.current = new maplibregl.Marker({ element: el, draggable: true, anchor: "bottom" }).setLngLat([punto.lng, punto.lat]).addTo(m);
      pin.current.on("dragend", () => {
        const p = pin.current!.getLngLat();
        cb.current({ lat: p.lat, lng: p.lng });
      });
    } else {
      pin.current.setLngLat([punto.lng, punto.lat]);
    }
    m.easeTo({ center: [punto.lng, punto.lat], zoom: Math.max(m.getZoom(), 13.5), duration: 800 });
  }, [punto]);

  return (
    <div className="relative h-56 overflow-hidden rounded-xl border border-borde">
      <div ref={div} className="h-full w-full" />
    </div>
  );
}
