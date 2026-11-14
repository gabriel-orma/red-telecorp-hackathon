import { useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import type { DetalleColectivo, EstadoColectivo } from "../../lib/api";
import { ESTADO_COLECTIVO, PRIORIDAD } from "../../lib/estados";
import { cn } from "../../lib/utils";

const DURACION_MS = 12_000; // la reproducción completa dura 12 s, sin importar cuánto duró el incidente
const hora = (t: number) => new Date(t).toLocaleTimeString("es-PE", { timeZone: "America/Lima", hour: "2-digit", minute: "2-digit", second: "2-digit" });

/** Reproducción del historial: un deslizador de tiempo que muestra cómo evolucionó el incidente. */
/** Texto legible de un evento. El detalle de un aviso enviado es JSON ({asunto, mensaje, canales}): se muestra el asunto. */
function textoDeEvento(e: { tipoEvento: string; detalle: string }): string {
  if (e.tipoEvento === "NOTIFICACION_ENVIADA") {
    try { const d = JSON.parse(e.detalle); if (d?.asunto) return `Aviso enviado: ${d.asunto}`; } catch { /* detalle en texto plano */ }
  }
  return e.detalle || e.tipoEvento.toLowerCase().replace(/_/g, " ");
}

export function Reproduccion({ detalle }: { detalle: DetalleColectivo }) {
  const c = detalle.colectivo;
  const reportes = useMemo(() => detalle.incidencias.map((i) => Date.parse(i.creadaEn)).sort((a, b) => a - b), [detalle.incidencias]);
  const eventos = useMemo(() => [...detalle.historial].sort((a, b) => a.ocurridoEn.localeCompare(b.ocurridoEn)), [detalle.historial]);
  // Desde el primer reporte, pero como mucho 30 min antes de la detección (reportes viejos alargarían la reproducción).
  const detectado = Date.parse(c.detectadoEn);
  const inicio = Math.max(detectado - 30 * 60_000, Math.min(detectado, reportes[0] ?? Infinity));
  const fin = c.resueltoEn ? Date.parse(c.resueltoEn) : Date.now();
  const [t, setT] = useState(fin);
  const [reproduciendo, setReproduciendo] = useState(false);
  const frame = useRef(0);

  useEffect(() => {
    if (!reproduciendo) return;
    const desde = performance.now(), t0 = t >= fin ? inicio : t;
    const paso = (ahora: number) => {
      const nuevo = t0 + ((ahora - desde) / DURACION_MS) * (fin - inicio);
      if (nuevo >= fin) { setT(fin); setReproduciendo(false); return; }
      setT(nuevo);
      frame.current = requestAnimationFrame(paso);
    };
    frame.current = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(frame.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reproduciendo]);

  // Estado del incidente en el instante t (derivado del historial inmutable).
  const hasta = eventos.filter((e) => Date.parse(e.ocurridoEn) <= t);
  const estado = ([...hasta].reverse().find((e) => e.tipoEvento === "CAMBIO_ESTADO")?.estadoNuevo as EstadoColectivo | undefined)
    ?? (hasta.length ? "EN_EVALUACION" : undefined);
  const nReportes = reportes.filter((r) => r <= t).length;
  const nAntenas = hasta.filter((e) => e.tipoEvento === "COMENTARIO" && e.detalle.startsWith("Antena ")).length;
  const prioridadTxt = [...hasta].reverse().find((e) => e.tipoEvento === "PRIORIDAD_ASIGNADA")?.detalle ?? "";
  const prioridad = (Object.keys(PRIORIDAD) as (keyof typeof PRIORIDAD)[]).find((p) => prioridadTxt.includes(p));
  const ultimo = hasta[hasta.length - 1];
  const pct = fin > inicio ? ((t - inicio) / (fin - inicio)) * 100 : 100;

  // Mini gráfico: reportes acumulados en el tiempo.
  const W = 300, H = 40;
  const puntos = reportes.map((r, i) => `${(((r - inicio) / Math.max(1, fin - inicio)) * W).toFixed(1)},${(H - ((i + 1) / Math.max(1, reportes.length)) * H).toFixed(1)}`);

  return (
    <div className="neu p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm text-tenue">Reproducción del incidente</span>
        <span className="cifra text-xs text-tenue">{hora(t)}</span>
      </div>

      <div className="grid grid-cols-4 gap-2 text-center">
        <Dato etiqueta="Estado" valor={estado ? ESTADO_COLECTIVO[estado].etiqueta : "—"} color={estado ? ESTADO_COLECTIVO[estado].color : undefined} />
        <Dato etiqueta="Reportes" valor={String(nReportes)} />
        <Dato etiqueta="Antenas en falla" valor={String(nAntenas)} />
        <Dato etiqueta="Prioridad" valor={prioridad ? PRIORIDAD[prioridad].etiqueta : "—"} color={prioridad ? PRIORIDAD[prioridad].color : undefined} />
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 h-10 w-full overflow-visible" preserveAspectRatio="none">
        {puntos.length > 0 && <polyline points={`0,${H} ${puntos.join(" ")}`} fill="none" stroke="#a78bfa" strokeOpacity=".35" strokeWidth="1.5" />}
        <clipPath id="recorte-repro"><rect x="0" y="0" width={(pct / 100) * W} height={H} /></clipPath>
        {puntos.length > 0 && <polyline points={`0,${H} ${puntos.join(" ")}`} fill="none" stroke="url(#linea-neu-repro)" strokeWidth="2.2" clipPath="url(#recorte-repro)" />}
        <defs><linearGradient id="linea-neu-repro"><stop offset="0" stopColor="#7c5cff" /><stop offset="1" stopColor="#e05ab0" /></linearGradient></defs>
      </svg>

      <div className="mt-2 flex items-center gap-3">
        <button onClick={() => setReproduciendo(!reproduciendo)} aria-label={reproduciendo ? "Pausar" : "Reproducir"}
          className="degradado grid size-10 shrink-0 place-items-center rounded-full text-white">
          {reproduciendo ? <Pause className="size-4" /> : <Play className="ml-0.5 size-4" />}
        </button>
        <input type="range" min={inicio} max={fin} step={Math.max(1, (fin - inicio) / 500)} value={t}
          onChange={(e) => { setReproduciendo(false); setT(Number(e.target.value)); }}
          aria-label="Momento del incidente" className="h-2 flex-1 cursor-pointer accent-[#a78bfa]" />
        <button onClick={() => { setReproduciendo(false); setT(inicio); }} aria-label="Al inicio" className="boton-neu grid size-9 place-items-center text-tenue"><RotateCcw className="size-3.5" /></button>
      </div>

      <div className={cn("mt-3 min-h-9 rounded-xl px-3 py-2 text-xs", ultimo ? "neu-hundido" : "")}>
        {ultimo ? <><span className="text-tenue">{hora(Date.parse(ultimo.ocurridoEn))} · </span>{textoDeEvento(ultimo)}{ultimo.estadoNuevo && ` → ${ultimo.estadoNuevo.toLowerCase().replace(/_/g, " ")}`}</>
          : <span className="text-tenue">Arrastra el deslizador o pulsa play para ver cómo evolucionó el incidente.</span>}
      </div>
    </div>
  );
}

function Dato({ etiqueta, valor, color }: { etiqueta: string; valor: string; color?: string }) {
  return (
    <div className="neu-hundido px-1 py-2">
      <div className="truncate text-sm font-semibold" style={{ color }}>{valor}</div>
      <div className="text-[10px] text-tenue">{etiqueta}</div>
    </div>
  );
}
