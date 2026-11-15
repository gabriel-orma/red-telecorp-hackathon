import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CloudLightning, FastForward, Loader2, PlugZap, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { apiEscenarios, type EstadoEscenario, type TipoEscenario, type Zona } from "../../lib/api";
import { usePolling } from "../../hooks/usePolling";
import { cn } from "../../lib/utils";

const TIPOS: Record<TipoEscenario, { etiqueta: string; icono: typeof CloudLightning; detalle: string }> = {
  TORMENTA: { etiqueta: "Tormenta", icono: CloudLightning, detalle: "Caídas y saturación en la zona y sus vecinas" },
  CORTE_ENERGIA: { etiqueta: "Corte de energía", icono: PlugZap, detalle: "Las antenas de la zona se apagan una a una" },
  ACELERADA: { etiqueta: "Acelerada", icono: FastForward, detalle: "3 min, 4 eventos encadenados empezando por la zona elegida: detección, priorización, recuperación y cierre automáticos (1 s cuenta como 1 min para la prioridad)" },
};

/** Botón "Simular" del mapa: lanza una tormenta o un corte de energía y muestra su avance. */
export function ControlEscenario({ zonas, zonaSugerida, onCambio }: { zonas: Zona[]; zonaSugerida?: string; onCambio: () => void }) {
  const estado = usePolling<EstadoEscenario>(useCallback(() => apiEscenarios.estado(), []), 3000);
  const [abierto, setAbierto] = useState(false);
  const [tipo, setTipo] = useState<TipoEscenario>("TORMENTA");
  const [zonaId, setZonaId] = useState(zonaSugerida ?? "ZONA-05");
  const [ocupado, setOcupado] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  const e = estado.datos;
  const enCurso = !!e?.activo;

  useEffect(() => { if (zonaSugerida) setZonaId(zonaSugerida); }, [zonaSugerida]);
  useEffect(() => {
    if (!abierto) return;
    const fuera = (ev: MouseEvent) => { if (!caja.current?.contains(ev.target as Node)) setAbierto(false); };
    const esc = (ev: KeyboardEvent) => { if (ev.key === "Escape") setAbierto(false); };
    document.addEventListener("mousedown", fuera); document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fuera); document.removeEventListener("keydown", esc); };
  }, [abierto]);

  const lanzar = async () => {
    setOcupado(true);
    try {
      await apiEscenarios.lanzar(tipo, zonaId);
      setAbierto(false);
      toast.custom(() => <Aviso texto={`${TIPOS[tipo].etiqueta} en ${zonas.find((z) => z.zonaId === zonaId)?.nombre}: comienza en segundos`} />, { duration: 5000 });
      await estado.refrescar(); onCambio();
    } catch (err) { toast.custom(() => <Aviso texto={err instanceof Error ? err.message : String(err)} />); }
    finally { setOcupado(false); }
  };
  const reiniciar = async () => {
    setOcupado(true);
    try {
      const r = await apiEscenarios.reiniciar();
      toast.custom(() => <Aviso texto={`Demo reiniciada · ${r.colectivosRestablecidos} incidente(s) simulado(s) en cierre`} />, { duration: 5000 });
      await estado.refrescar(); setTimeout(onCambio, 1500);
    } catch (err) { toast.custom(() => <Aviso texto={`No se pudo reiniciar la demo: ${err instanceof Error ? err.message : String(err)}`} />); }
    finally { setOcupado(false); }
  };

  return (
    <div ref={caja} className="relative flex items-center gap-2">
      <AnimatePresence initial={false} mode="popLayout">
        {enCurso ? (
          <motion.div key="curso" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            className="neu-chico flex h-11 items-center gap-3 px-4">
            {(() => { const I = TIPOS[e!.tipo ?? "TORMENTA"].icono; return <I className="latido size-4 text-[#e05ab0]" />; })()}
            <div className="text-xs leading-tight">
              <div className="font-semibold">{TIPOS[e!.tipo ?? "TORMENTA"].etiqueta} en curso</div>
              <div className="max-w-[260px] truncate text-[10px] text-tenue">
                {e!.tipo === "ACELERADA" ? `Paso ${e!.oleada ?? 0} de ${e!.total ?? "…"} · ${e!.narrativa ?? "preparando"}` : `Oleada ${e!.oleada ?? 0} de ${e!.total ?? "…"}`} · {e!.reportes ?? 0} reportes · {e!.antenas ?? 0} antenas
              </div>
            </div>
            <div className="neu-hundido h-1.5 w-16 overflow-hidden rounded-full">
              <motion.div className="degradado h-full" animate={{ width: `${(100 * (e!.oleada ?? 0)) / (e!.total || 1)}%` }} />
            </div>
          </motion.div>
        ) : (
          <motion.button key="simular" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            onClick={() => setAbierto(!abierto)} data-activo={abierto}
            className="boton-neu flex h-11 items-center gap-2 px-4 text-xs font-semibold text-texto">
            <CloudLightning className="size-4 text-[#e05ab0]" /> Simular escenario
          </motion.button>
        )}
      </AnimatePresence>
      <button onClick={reiniciar} disabled={ocupado} title="Reiniciar demo: quita las fallas forzadas y cierra solo los incidentes simulados (los reales no se tocan)" aria-label="Reiniciar demo"
        className="boton-neu grid size-11 place-items-center text-tenue disabled:opacity-50">
        {ocupado && !abierto ? <Loader2 className="size-4 animate-spin" /> : <RotateCcw className="size-4" />}
      </button>

      <AnimatePresence>
        {abierto && !enCurso && (
          <motion.div initial={{ opacity: 0, y: -6, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: 0.97 }}
            transition={{ duration: 0.16, ease: [0.23, 1, 0.32, 1] }}
            className="neu absolute right-0 top-14 z-30 w-80 origin-top-right space-y-3 p-4">
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(TIPOS) as TipoEscenario[]).map((t) => {
                const I = TIPOS[t].icono;
                return (
                  <button key={t} onClick={() => setTipo(t)} data-activo={tipo === t}
                    className={cn("boton-neu flex flex-col items-center gap-1.5 py-3 text-xs", tipo === t ? "text-acento" : "text-tenue")}>
                    <I className="size-5" /> {TIPOS[t].etiqueta}
                  </button>
                );
              })}
            </div>
            <p className="text-[11px] text-tenue">{TIPOS[tipo].detalle}.</p>
            <label className="block text-[11px] text-tenue">Zona
              <select value={zonaId} onChange={(ev) => setZonaId(ev.target.value)}
                className="mt-1 w-full rounded-xl px-3 py-2.5 text-sm text-texto outline-none">
                {zonas.map((z) => <option key={z.zonaId} value={z.zonaId}>{z.nombre}</option>)}
              </select>
            </label>
            <button onClick={lanzar} disabled={ocupado}
              className="degradado flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-white disabled:opacity-60">
              {ocupado && <Loader2 className="size-4 animate-spin" />} Iniciar
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Aviso({ texto }: { texto: string }) {
  return <div className="tema-neu neu-chico px-4 py-3 text-sm">{texto}</div>;
}
