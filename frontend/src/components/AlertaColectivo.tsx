import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Siren, X } from "lucide-react";
import type { Colectivo } from "../lib/api";
import { PRIORIDAD } from "../lib/estados";
import { navegar } from "../lib/router";

/** Dos tonos cortos con WebAudio (sin archivos). El navegador puede bloquearlo hasta la primera interacción. */
function sonarAlerta() {
  try {
    const ctx = new AudioContext();
    [0, 0.22].forEach((t, i) => {
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = i ? 660 : 880;
      g.gain.setValueAtTime(0.0001, ctx.currentTime + t);
      g.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + t + 0.2);
      osc.connect(g).connect(ctx.destination);
      osc.start(ctx.currentTime + t);
      osc.stop(ctx.currentTime + t + 0.22);
    });
  } catch { /* sin audio */ }
}

/** Banner rojo cuando aparece un incidente colectivo nuevo (comparando con los ya vistos). */
export function AlertaColectivo({ colectivos }: { colectivos: Colectivo[] | null }) {
  const vistos = useRef<Set<string> | null>(null);
  const [alerta, setAlerta] = useState<Colectivo | null>(null);

  useEffect(() => {
    if (!colectivos) return;
    const ids = new Set(colectivos.map((c) => c.incidenteColectivoId));
    if (vistos.current === null) { vistos.current = ids; return; } // la primera carga no alerta
    const nuevo = colectivos.find((c) => !vistos.current!.has(c.incidenteColectivoId));
    vistos.current = new Set([...vistos.current, ...ids]);
    if (nuevo) { setAlerta(nuevo); sonarAlerta(); }
  }, [colectivos]);

  useEffect(() => {
    if (!alerta) return;
    const t = setTimeout(() => setAlerta(null), 15_000);
    return () => clearTimeout(t);
  }, [alerta]);

  return (
    <AnimatePresence>
      {alerta && (
        <motion.div
          initial={{ y: -80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -80, opacity: 0 }}
          className="fixed left-1/2 top-3 z-50 w-[min(560px,calc(100%-24px))] -translate-x-1/2"
        >
          <div className="flex items-center gap-3 rounded-2xl border border-caida/60 bg-[#2a0b10]/95 px-4 py-3 shadow-[0_0_40px_#ef444466] backdrop-blur">
            <div className="latido grid size-10 shrink-0 place-items-center rounded-xl bg-caida/20 text-caida"><Siren className="size-5" /></div>
            <button className="min-w-0 flex-1 text-left" onClick={() => { navegar(`/colectivos?id=${alerta.incidenteColectivoId}`); setAlerta(null); }}>
              <div className="text-sm font-semibold text-caida">Incidente colectivo detectado · {alerta.zona.nombre}</div>
              <div className="truncate text-xs text-texto/80">{alerta.origenDetalle}</div>
              <div className="mt-0.5 text-[11px] text-tenue">
                Prioridad <b style={{ color: PRIORIDAD[alerta.prioridad].color }}>{PRIORIDAD[alerta.prioridad].etiqueta}</b> · clic para ver el flujo
              </div>
            </button>
            <button onClick={() => setAlerta(null)} className="rounded-md p-1 text-tenue hover:text-texto" aria-label="Cerrar"><X className="size-4" /></button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
