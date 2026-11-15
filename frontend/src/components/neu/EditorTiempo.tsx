import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { AudioLines, Pause, Play, Siren, SkipBack, TowerControl, ZoomIn, ZoomOut } from "lucide-react";
import { ESTADO_COLECTIVO, PRIORIDAD } from "../../lib/estados";
import { carriles, tramosAntenas, type Linea } from "../../lib/lineaTiempo";
import { cn } from "../../lib/utils";
import { COLOR_NEU } from "./paleta";

// Editor de línea de tiempo estilo editor de video: regla, cabezal que se arrastra y tres pistas.
//   Incidentes → clips por incidente colectivo (color = prioridad de cada momento, rombos = cambios de estado)
//   Antenas    → clips por tramo en falla o saturación
//   Reportes   → "onda de audio" con la cantidad de reportes por instante
// Los clips se recalculan solo cuando cambian los datos o el ancho; mover el cabezal solo mueve una línea.

export const VELOCIDADES = [1, 10, 60, 300] as const;
export const VENTANAS = [{ horas: 0.25, etiqueta: "15 min" }, { horas: 1, etiqueta: "1 h" }, { horas: 6, etiqueta: "6 h" }, { horas: 24, etiqueta: "24 h" }];
const ANCHO_CABECERA = 116;
const ALTO_REGLA = 26;
const ALTO_CLIP = 24, ALTO_ANTENA = 16, ALTO_ONDA = 64;
const PASOS_REGLA = [10, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600].map((s) => s * 1000);

const fmtHora = (t: number, segundos: boolean) => new Date(t).toLocaleTimeString("es-PE", {
  timeZone: "America/Lima", hour: "2-digit", minute: "2-digit", ...(segundos ? { second: "2-digit" } : {}), hour12: false,
});

interface Props {
  linea: Linea | null;
  desde: number;
  hasta: number;
  t: number;
  onT: (t: number) => void;
  reproduciendo: boolean;
  onReproducir: (r: boolean) => void;
  velocidad: number;
  onVelocidad: (v: number) => void;
  horas: number;
  onHoras: (h: number) => void;
  enVivo: boolean;
  onEnVivo: () => void;
  cargando: boolean;
  seleccion: string | null;
  onColectivo: (id: string) => void;
}

export function EditorTiempo(p: Props) {
  const { desde, hasta, t } = p;
  const visor = useRef<HTMLDivElement>(null);
  const [ancho, setAncho] = useState(800);
  const [zoom, setZoom] = useState(1);
  const arrastrando = useRef(false);
  const W = Math.max(200, (ancho - ANCHO_CABECERA) * zoom);
  const span = Math.max(1, hasta - desde);
  const x = (tt: number) => ((tt - desde) / span) * W;

  useLayoutEffect(() => {
    const el = visor.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setAncho(el.clientWidth));
    ro.observe(el);
    setAncho(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  // Si el cabezal sale de la vista mientras reproduce o sigue en vivo, desplazar (como un editor real).
  const xCabezal = x(t);
  const clipsCol = useMemo(() => {
    if (!p.linea) return [];
    return carriles(p.linea.colectivos.map((c) => ({ ...c, desde: c.inicio, hasta: c.fin ?? hasta })), 4);
  }, [p.linea, hasta]);
  const clipsAnt = useMemo(() => (p.linea ? carriles(tramosAntenas(p.linea, hasta), 5) : []), [p.linea, hasta]);
  const altoCol = Math.max(1, ...clipsCol.map((c) => c.carril + 1)) * (ALTO_CLIP + 4) + 8;
  const altoAnt = Math.max(1, ...clipsAnt.map((c) => c.carril + 1)) * (ALTO_ANTENA + 3) + 8;
  const alto = useMemo(() => ({ col: altoCol, ant: altoAnt }), [altoCol, altoAnt]);
  useEffect(() => {
    const el = visor.current;
    if (!el || arrastrando.current || zoom === 1) return;
    const izq = el.scrollLeft, der = izq + el.clientWidth - ANCHO_CABECERA;
    if (xCabezal < izq || xCabezal > der - 24) el.scrollLeft = Math.max(0, xCabezal - (el.clientWidth - ANCHO_CABECERA) * 0.7);
  }, [xCabezal, zoom]);

  // Arrastrar el cabezal sobre la regla o las pistas. Manejadores estables (vía ref) para que las pistas
  // memorizadas no se redibujen en cada cuadro de la reproducción.
  const vivo = useRef({ p, desde, span, W });
  vivo.current = { p, desde, span, W };
  const tDesdeEvento = (e: React.PointerEvent) => {
    const el = visor.current!, v = vivo.current;
    const rel = e.clientX - el.getBoundingClientRect().left - ANCHO_CABECERA + el.scrollLeft;
    return v.desde + Math.min(1, Math.max(0, rel / v.W)) * v.span;
  };
  const alPresionar = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;
    arrastrando.current = true;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    vivo.current.p.onReproducir(false);
    vivo.current.p.onT(tDesdeEvento(e));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const alMover = useCallback((e: React.PointerEvent) => { if (arrastrando.current) vivo.current.p.onT(tDesdeEvento(e)); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const alSoltar = useCallback(() => { arrastrando.current = false; }, []);
  const alColectivo = useCallback((id: string) => vivo.current.p.onColectivo(id), []);

  const zoomEn = (factor: number) => {
    const el = visor.current;
    const nuevo = Math.min(48, Math.max(1, zoom * factor));
    setZoom(nuevo);
    // Mantener el cabezal en el mismo lugar de la pantalla al hacer zoom.
    if (el) requestAnimationFrame(() => { el.scrollLeft = Math.max(0, (xCabezal / W) * W * (nuevo / zoom) - (el.clientWidth - ANCHO_CABECERA) / 2); });
  };

  const teclado = (e: React.KeyboardEvent) => {
    if (e.target !== e.currentTarget) return;   // Espacio/flechas en un botón hijo activan ese botón, no el atajo de la línea de tiempo
    const paso = span / 200;
    if (e.key === " ") { e.preventDefault(); p.onReproducir(!p.reproduciendo); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); p.onReproducir(false); p.onT(Math.max(desde, t - paso * (e.shiftKey ? 10 : 1))); }
    else if (e.key === "ArrowRight") { e.preventDefault(); p.onReproducir(false); p.onT(Math.min(hasta, t + paso * (e.shiftKey ? 10 : 1))); }
    else if (e.key === "Home") { e.preventDefault(); p.onReproducir(false); p.onT(desde); }
    else if (e.key === "End") { e.preventDefault(); p.onEnVivo(); }
  };

  return (
    <section className="neu flex shrink-0 flex-col p-3 outline-none focus-visible:ring-2 focus-visible:ring-acento/50" onKeyDown={teclado} tabIndex={0} aria-label="Línea de tiempo (espacio: reproducir, flechas: mover el cabezal)">
      {/* Barra de transporte */}
      <div className="flex flex-wrap items-center gap-2 pb-3">
        <button onClick={() => { p.onReproducir(false); p.onT(desde); }} aria-label="Al inicio" className="boton-neu grid size-9 place-items-center text-tenue"><SkipBack className="size-4" /></button>
        <button onClick={() => p.onReproducir(!p.reproduciendo)} aria-label={p.reproduciendo ? "Pausar" : "Reproducir"}
          className="degradado grid size-10 place-items-center rounded-full text-white">
          {p.reproduciendo ? <Pause className="size-4" /> : <Play className="ml-0.5 size-4" />}
        </button>
        <button onClick={p.onEnVivo} data-activo={p.enVivo}
          className={cn("boton-neu flex h-9 items-center gap-2 px-3 text-xs font-semibold", p.enVivo ? "text-caida" : "text-tenue")}>
          <span className={cn("size-2 rounded-full", p.enVivo ? "latido bg-caida" : "bg-tenue/50")} /> En vivo
        </button>
        <div className="neu-hundido ml-1 flex h-9 items-center rounded-xl px-3">
          <span className="cifra text-sm font-semibold tabular-nums">{fmtHora(t, true)}</span>
          <span className="ml-2 text-[10px] text-tenue">{p.enVivo ? "ahora" : `−${formatoDuracion(Date.now() - t)}`}</span>
        </div>

        <Segmentado etiqueta="Velocidad" opciones={VELOCIDADES.map((v) => ({ valor: v, texto: `${v}×` }))} valor={p.velocidad} onCambio={p.onVelocidad} />
        <Segmentado etiqueta="Ventana" opciones={VENTANAS.map((v) => ({ valor: v.horas, texto: v.etiqueta }))} valor={p.horas} onCambio={p.onHoras} />
        <div className="ml-auto flex items-center gap-1">
          {p.cargando && <span className="mr-2 text-[10px] text-tenue">actualizando…</span>}
          <button onClick={() => zoomEn(1 / 1.6)} disabled={zoom <= 1} aria-label="Alejar" className="boton-neu grid size-9 place-items-center text-tenue disabled:opacity-40"><ZoomOut className="size-4" /></button>
          <span className="w-10 text-center text-[10px] text-tenue">{zoom.toFixed(zoom < 10 ? 1 : 0)}×</span>
          <button onClick={() => zoomEn(1.6)} disabled={zoom >= 48} aria-label="Acercar" className="boton-neu grid size-9 place-items-center text-tenue disabled:opacity-40"><ZoomIn className="size-4" /></button>
        </div>
      </div>

      {/* Pistas */}
      <div ref={visor} className="scroll-fino neu-hundido relative min-h-0 overflow-x-auto overflow-y-hidden rounded-2xl">
        <div className="relative flex" style={{ width: W + ANCHO_CABECERA }}>
          <Pistas linea={p.linea} clipsCol={clipsCol} clipsAnt={clipsAnt} alto={alto} desde={desde} hasta={hasta} W={W} seleccion={p.seleccion} onColectivo={alColectivo}
            onPresionar={alPresionar} onMover={alMover} onSoltar={alSoltar} />
          {/* Cabezal: la única pieza que se mueve en cada cuadro */}
          <div className="pointer-events-none absolute inset-y-0 z-20" style={{ left: ANCHO_CABECERA, width: W }}>
            <OndaReproducida linea={p.linea} desde={desde} hasta={hasta} W={W} xCabezal={xCabezal} top={ALTO_REGLA + alto.col + alto.ant} />
            <div className="absolute inset-y-0 w-px bg-[#f472b6] shadow-[0_0_8px_#f472b6]" style={{ transform: `translateX(${xCabezal}px)` }}>
              <div className="absolute -left-[7px] top-0 h-4 w-[15px] rounded-b-md bg-gradient-to-b from-[#a78bfa] to-[#f472b6]" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function formatoDuracion(ms: number) {
  const s = Math.max(0, Math.round(ms / 1000));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, "0")} s`;
  return `${Math.floor(s / 3600)} h ${String(Math.floor((s % 3600) / 60)).padStart(2, "0")} min`;
}

function Segmentado<T extends number>({ etiqueta, opciones, valor, onCambio }: { etiqueta: string; opciones: { valor: T; texto: string }[]; valor: T; onCambio: (v: T) => void }) {
  return (
    <div role="radiogroup" aria-label={etiqueta} className="neu-hundido flex h-9 items-center gap-0.5 rounded-xl p-1">
      {opciones.map((o) => (
        <button key={o.valor} role="radio" aria-checked={o.valor === valor} onClick={() => onCambio(o.valor)}
          className={cn("h-7 rounded-lg px-2.5 text-[11px] font-medium transition-colors", o.valor === valor ? "degradado text-white" : "text-tenue hover:text-texto")}>
          {o.texto}
        </button>
      ))}
    </div>
  );
}

type ClipCol = Linea["colectivos"][number] & { desde: number; hasta: number; carril: number };
type ClipAnt = ReturnType<typeof tramosAntenas>[number] & { carril: number };

interface PropsPistas {
  linea: Linea | null; clipsCol: ClipCol[]; clipsAnt: ClipAnt[]; alto: { col: number; ant: number }; desde: number; hasta: number; W: number; seleccion: string | null;
  onColectivo: (id: string) => void;
  onPresionar: (e: React.PointerEvent) => void; onMover: (e: React.PointerEvent) => void; onSoltar: () => void;
}

/** Regla + pistas. Memorizado: no se vuelve a dibujar cuando solo se mueve el cabezal. */
const Pistas = memo(function Pistas({ linea, clipsCol, clipsAnt, alto, desde, hasta, W, seleccion, onColectivo, onPresionar, onMover, onSoltar }: PropsPistas) {
  const span = Math.max(1, hasta - desde);
  const x = (tt: number) => ((tt - desde) / span) * W;

  // Regla: el paso más fino que deje ~90 px entre marcas.
  const paso = PASOS_REGLA.find((s) => (s / span) * W >= 90) ?? PASOS_REGLA[PASOS_REGLA.length - 1];
  const offsetLima = 5 * 3600_000; // alinear las marcas a la hora de Lima (UTC−5)
  const marcas: number[] = [];
  for (let m = Math.ceil((desde - offsetLima) / paso) * paso + offsetLima; m <= hasta; m += paso) marcas.push(m);

  const filas = [
    { clave: "col", etiqueta: "Incidentes", icono: Siren, alto: alto.col },
    { clave: "ant", etiqueta: "Antenas", icono: TowerControl, alto: alto.ant },
    { clave: "rep", etiqueta: "Reportes", icono: AudioLines, alto: ALTO_ONDA + 8 },
  ];

  return (
    <>
      {/* Cabeceras de pista (fijas al desplazar) */}
      <div className="sticky left-0 z-30 shrink-0 border-r border-white/5 bg-fondo" style={{ width: ANCHO_CABECERA }}>
        <div style={{ height: ALTO_REGLA }} className="border-b border-white/5" />
        {filas.map((f) => (
          <div key={f.clave} style={{ height: f.alto }} className="flex items-start gap-2 border-b border-white/5 px-3 pt-2 text-[11px] font-medium text-tenue">
            <f.icono className="size-3.5 shrink-0 text-acento" /> {f.etiqueta}
          </div>
        ))}
      </div>

      <div className="relative cursor-ew-resize touch-none select-none" style={{ width: W }}
        onPointerDown={onPresionar} onPointerMove={onMover} onPointerUp={onSoltar} onPointerCancel={onSoltar}>
        {/* Regla */}
        <div className="relative border-b border-white/5" style={{ height: ALTO_REGLA }}>
          {marcas.map((m) => (
            <div key={m} className="absolute top-0 h-full" style={{ left: x(m) }}>
              <div className="h-2 w-px bg-white/25" />
              <span className="absolute left-1 top-1.5 whitespace-nowrap font-mono text-[9px] text-tenue">{fmtHora(m, paso < 60_000)}</span>
            </div>
          ))}
        </div>
        {/* Líneas guía verticales */}
        <div className="pointer-events-none absolute inset-0" style={{ top: ALTO_REGLA }}>
          {marcas.map((m) => <div key={m} className="absolute inset-y-0 w-px bg-white/[0.035]" style={{ left: x(m) }} />)}
        </div>

        {/* Pista de incidentes */}
        <div className="relative border-b border-white/5" style={{ height: alto.col }}>
          {clipsCol.map((c) => {
            const izq = x(c.desde), ancho = Math.max(6, x(c.hasta) - izq);
            const tramos = c.prioridades.length ? c.prioridades : [{ t: c.inicio, prioridad: c.prioridadFinal }];
            return (
              <button key={c.id} title={`${c.zonaNombre} · ${c.afectados} afectados · ${PRIORIDAD[c.prioridadFinal].etiqueta}`}
                onPointerDown={(e) => e.stopPropagation()}
                onClick={() => onColectivo(c.id)}
                className={cn("absolute overflow-hidden rounded-md text-left ring-1 ring-white/10 transition-shadow",
                  seleccion === c.id && "ring-2 ring-white/80")}
                style={{ left: izq, width: ancho, top: 4 + c.carril * (ALTO_CLIP + 4), height: ALTO_CLIP }}>
                {/* Color por tramo de prioridad: se ve la escalada BAJA → CRÍTICA */}
                {tramos.map((pr, i) => {
                  const ini = Math.max(c.desde, i === 0 ? c.desde : pr.t);
                  const fin = tramos[i + 1]?.t ?? c.hasta;
                  return <span key={i} className="absolute inset-y-0" style={{ left: x(ini) - izq, width: Math.max(0, x(fin) - x(ini)), background: `${PRIORIDAD[pr.prioridad].color}55` }} />;
                })}
                <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: PRIORIDAD[c.prioridadFinal].color }} />
                {/* Rombos: cambios de estado (como keyframes) */}
                {c.estados.slice(1).map((e, i) => (
                  <span key={i} className="absolute top-1/2 size-[7px] -translate-x-1/2 -translate-y-1/2 rotate-45"
                    style={{ left: x(e.t) - izq, background: ESTADO_COLECTIVO[e.estado].color }} />
                ))}
                {c.fin === null && <span className="latido absolute inset-y-0 right-0 w-1 bg-white/60" />}
                <span className="relative block truncate px-2 text-[10px] font-semibold leading-6 text-white/90">
                  {ancho > 50 ? `${c.zonaNombre} · ${c.afectados} af.` : ""}
                </span>
              </button>
            );
          })}
          {!clipsCol.length && <Vacio texto="Sin incidentes colectivos en esta ventana" />}
        </div>

        {/* Pista de antenas */}
        <div className="relative border-b border-white/5" style={{ height: alto.ant }}>
          {clipsAnt.map((a, i) => {
            const izq = x(a.desde), ancho = Math.max(3, x(a.hasta) - izq);
            return (
              <div key={`${a.antenaId}-${a.desde}-${i}`} title={`${a.antenaId} · ${a.estado.toLowerCase()}`}
                className="absolute overflow-hidden rounded-[4px]"
                style={{ left: izq, width: ancho, top: 4 + a.carril * (ALTO_ANTENA + 3), height: ALTO_ANTENA,
                  background: `${COLOR_NEU[a.estado]}${a.estado === "SATURADA" ? "40" : "70"}`, borderLeft: `2px solid ${COLOR_NEU[a.estado]}` }}>
                {ancho > 46 && <span className="block truncate px-1.5 font-mono text-[9px] leading-4 text-white/85">{a.antenaId}</span>}
              </div>
            );
          })}
          {!clipsAnt.length && <Vacio texto="Todas las antenas normales" />}
        </div>

        {/* Pista de reportes: onda (la parte ya reproducida se colorea en la capa del cabezal) */}
        <div className="relative" style={{ height: ALTO_ONDA + 8 }}>
          <Onda linea={linea} desde={desde} hasta={hasta} W={W} color="rgba(167,139,250,0.22)" />
        </div>
      </div>
    </>
  );
});

function Vacio({ texto }: { texto: string }) {
  return <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[10px] text-tenue/60">{texto}</span>;
}

/** Cantidad de reportes por columna de ~3 px, en espejo (como la forma de onda de un audio). */
function barrasOnda(linea: Linea | null, desde: number, hasta: number, W: number) {
  if (!linea) return { barras: [] as number[], ancho: 3 };
  const ancho = 3, n = Math.max(1, Math.floor(W / ancho)), span = Math.max(1, hasta - desde);
  const cuenta = new Array<number>(n).fill(0);
  for (const t of linea.reportesTs) {
    if (t < desde || t > hasta) continue;
    cuenta[Math.min(n - 1, Math.floor(((t - desde) / span) * n))]++;
  }
  const max = Math.max(1, ...cuenta);
  return { barras: cuenta.map((c) => (c ? Math.max(0.12, Math.sqrt(c / max)) : 0)), ancho };
}

const Onda = memo(function Onda({ linea, desde, hasta, W, color, relleno }: { linea: Linea | null; desde: number; hasta: number; W: number; color?: string; relleno?: string }) {
  const { barras, ancho } = useMemo(() => barrasOnda(linea, desde, hasta, W), [linea, desde, hasta, W]);
  const medio = 4 + ALTO_ONDA / 2;
  return (
    <svg className="absolute inset-0" width={W} height={ALTO_ONDA + 8} aria-hidden>
      {barras.map((b, i) => b > 0 && (
        <rect key={i} x={i * ancho} y={medio - (b * ALTO_ONDA) / 2} width={ancho - 1} height={b * ALTO_ONDA} rx={1}
          fill={relleno ?? color} />
      ))}
    </svg>
  );
});

/** La parte de la onda a la izquierda del cabezal, con el degradado (lo "ya reproducido"). */
function OndaReproducida({ linea, desde, hasta, W, xCabezal, top }: { linea: Linea | null; desde: number; hasta: number; W: number; xCabezal: number; top: number }) {
  return (
    <div className="absolute left-0 overflow-hidden" style={{ top, height: ALTO_ONDA + 8, width: Math.max(0, xCabezal) }}>
      <Onda linea={linea} desde={desde} hasta={hasta} W={W} relleno="url(#degradado-onda)" />
      <svg width="0" height="0" className="absolute"><defs>
        <linearGradient id="degradado-onda" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#a78bfa" /><stop offset="1" stopColor="#f472b6" /></linearGradient>
      </defs></svg>
    </div>
  );
}

