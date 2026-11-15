// Línea de tiempo: estado de la red en cualquier instante t, calculado en el navegador.
// Los datos llegan una vez (GET /api/linea-tiempo) y se indexan por tiempo; mover el cabezal solo hace
// búsquedas binarias, sin pedir nada al servidor.
import type { DatosLineaTiempo, EstadoAntena, EstadoColectivo, Prioridad, Zona } from "./api";

export interface Linea {
  desde: number;
  hasta: number;
  reportes: { id: string; t: number; zonaId: string; lat: number; lng: number }[];
  reportesTs: number[];
  antenas: Map<string, { inicial: EstadoAntena; ts: number[]; estados: EstadoAntena[] }>;
  colectivos: {
    id: string; zonaId: string; zonaNombre: string; inicio: number; fin: number | null; afectados: number; origen: string;
    estados: { t: number; estado: EstadoColectivo }[]; prioridades: { t: number; prioridad: Prioridad }[]; prioridadFinal: Prioridad;
  }[];
}

/** Punto estable dentro de la zona para reportes sin GPS (mismo id → mismo punto). */
export function puntoEstable(id: string, z: Zona): { lat: number; lng: number } {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  const ang = (h % 360) * (Math.PI / 180), dist = (((h >> 9) % 100) / 100) * z.radioM * 0.7;
  return {
    lat: z.centro.lat + (dist * Math.sin(ang)) / 111320,
    lng: z.centro.lng + (dist * Math.cos(ang)) / (111320 * Math.cos((z.centro.lat * Math.PI) / 180)),
  };
}

export function indexar(d: DatosLineaTiempo, zonas: Zona[]): Linea {
  const porZona = new Map(zonas.map((z) => [z.zonaId, z]));
  const reportes = d.reportes.flatMap((r) => {
    const z = porZona.get(r.zonaId);
    const p = r.lat !== undefined && r.lng !== undefined ? { lat: r.lat, lng: r.lng } : z ? puntoEstable(r.id, z) : null;
    return p ? [{ id: r.id, t: Date.parse(r.t), zonaId: r.zonaId, ...p }] : [];
  }).sort((a, b) => a.t - b.t);
  const antenas = new Map(d.antenas.map((a) => [a.antenaId, {
    inicial: a.inicial, ts: a.cambios.map((c) => Date.parse(c.t)), estados: a.cambios.map((c) => c.estado),
  }]));
  const colectivos = d.colectivos.map((c) => ({
    id: c.id, zonaId: c.zonaId, zonaNombre: c.zonaNombre, afectados: c.afectados, origen: c.origen,
    inicio: Date.parse(c.inicio), fin: c.fin ? Date.parse(c.fin) : null, prioridadFinal: c.prioridad,
    estados: c.estados.map((e) => ({ t: Date.parse(e.t), estado: e.estado })),
    prioridades: c.prioridades.map((p) => ({ t: Date.parse(p.t), prioridad: p.prioridad })),
  }));
  return { desde: Date.parse(d.desde), hasta: Date.parse(d.hasta), reportes, reportesTs: reportes.map((r) => r.t), antenas, colectivos };
}

/** Último índice i con arr[i] <= t (o -1). */
export function ultimoHasta(arr: number[], t: number): number {
  let lo = 0, hi = arr.length - 1, r = -1;
  while (lo <= hi) {
    const m = (lo + hi) >> 1;
    if (arr[m] <= t) { r = m; lo = m + 1; } else hi = m - 1;
  }
  return r;
}

export function estadoAntenaEn(l: Linea, antenaId: string, t: number): EstadoAntena {
  const a = l.antenas.get(antenaId);
  if (!a) return "SIN_DATOS";
  const i = ultimoHasta(a.ts, t);
  return i < 0 ? a.inicial : a.estados[i];
}

function ultimoValor<T extends { t: number }>(lista: T[], t: number): T | undefined {
  let r: T | undefined;
  for (const x of lista) { if (x.t <= t) r = x; else break; }
  return r;
}

/** Colectivos abiertos en t, con su estado y prioridad de ese momento. */
export function colectivosEn(l: Linea, t: number) {
  return l.colectivos
    .filter((c) => c.inicio <= t && (c.fin === null || c.fin > t))
    .map((c) => ({
      ...c,
      estadoEn: ultimoValor(c.estados, t)?.estado ?? "EN_EVALUACION",
      prioridadEn: ultimoValor(c.prioridades, t)?.prioridad ?? "BAJA",
    }));
}

/** Reportes entre t - ventana y t, con su peso (1 = recién llegado, 0 = a punto de salir de la ventana). */
export function reportesEn(l: Linea, t: number, ventanaMs: number) {
  const ts = l.reportesTs;
  const fin = ultimoHasta(ts, t);
  const ini = ultimoHasta(ts, t - ventanaMs) + 1;
  return l.reportes.slice(ini, fin + 1).map((r) => ({ ...r, peso: 1 - (t - r.t) / ventanaMs }));
}

export interface Tramo { desde: number; hasta: number; estado: EstadoAntena; antenaId: string }

/** Tramos en falla o saturación de cada antena (los clips de la pista "Antenas"). */
export function tramosAntenas(l: Linea, hastaVista = l.hasta): Tramo[] {
  const salida: Tramo[] = [];
  for (const [antenaId, a] of l.antenas) {
    let estado = a.inicial, desde = l.desde;
    const cerrar = (hasta: number) => { if (estado !== "NORMAL" && estado !== "SIN_DATOS" && hasta > desde) salida.push({ antenaId, estado, desde, hasta }); };
    a.ts.forEach((t, i) => {
      if (a.estados[i] === estado) return;
      cerrar(t);
      estado = a.estados[i]; desde = t;
    });
    cerrar(Math.max(l.hasta, hastaVista));
  }
  return salida.sort((x, y) => x.desde - y.desde);
}

/** Reparte intervalos en carriles sin solaparse (como las pistas de un editor). */
export function carriles<T extends { desde: number; hasta: number }>(items: T[], maximo = 6): (T & { carril: number })[] {
  const finCarril: number[] = [];
  return items.map((it) => {
    let c = finCarril.findIndex((f) => f <= it.desde);
    if (c < 0) c = finCarril.length < maximo ? finCarril.length : finCarril.indexOf(Math.min(...finCarril));
    finCarril[c] = it.hasta;
    return { ...it, carril: c };
  });
}

/** Ventana del mapa de calor según el tramo visible: ~1/12 del total (entre 1 min y 1 h). */
export const ventanaCalor = (spanMs: number) => Math.min(60, Math.max(1, Math.round(spanMs / 12 / 60_000))) * 60_000;
