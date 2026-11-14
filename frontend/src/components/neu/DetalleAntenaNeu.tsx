import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { api, type Antena, type EstadoAntena, type Metrica, type Zona } from "../../lib/api";
import { ESTADO, TIPO_ZONA } from "../../lib/estados";
import { cn, haceCuanto } from "../../lib/utils";
import { COLOR_NEU } from "./paleta";
import { Cifra } from "./Piezas";

function Linea({ datos }: { datos: Metrica[] }) {
  const W = 260, H = 64, MAX = 170;
  if (datos.length < 2) return <div className="grid h-16 place-items-center text-xs text-tenue">Reuniendo lecturas…</div>;
  const x = (i: number) => (i / (datos.length - 1)) * W;
  const y = (v: number) => H - (Math.min(v, MAX) / MAX) * H;
  const d = datos.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.gbPorMinuto).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-16 w-full overflow-visible">
      <defs>
        <linearGradient id="linea-neu" x1="0" x2="1"><stop offset="0" stopColor="#7c5cff" /><stop offset="1" stopColor="#e05ab0" /></linearGradient>
        <linearGradient id="area-neu" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#a78bfa" stopOpacity=".3" /><stop offset="1" stopColor="#a78bfa" stopOpacity="0" /></linearGradient>
      </defs>
      <line x1="0" x2={W} y1={y(129)} y2={y(129)} stroke={COLOR_NEU.SATURADA} strokeOpacity=".35" strokeDasharray="3 4" />
      <line x1="0" x2={W} y1={y(60)} y2={y(60)} stroke={COLOR_NEU.CAIDA} strokeOpacity=".35" strokeDasharray="3 4" />
      <path d={`${d} L${W},${H} L0,${H} Z`} fill="url(#area-neu)" />
      <path d={d} fill="none" stroke="url(#linea-neu)" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

const ACCIONES: { etiqueta: string; valor: number | null; estado: EstadoAntena }[] = [
  { etiqueta: "Saturar", valor: 150, estado: "SATURADA" },
  { etiqueta: "Caída", valor: 35, estado: "CAIDA" },
  { etiqueta: "Apagar", valor: 0, estado: "INHABILITADA" },
];

interface Props {
  antena: Antena | null;
  zona: Zona | undefined;
  forzada: number | undefined;
  onCerrar: () => void;
  onForzar: (antenaId: string, valor: number | null) => Promise<void>;
}

/** Tarjeta flotante con el detalle de una antena (estilo neumórfico). */
export function DetalleAntenaNeu({ antena, zona, forzada, onCerrar, onForzar }: Props) {
  const [serie, setSerie] = useState<Metrica[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const id = antena?.antenaId;

  useEffect(() => {
    if (!id) return;
    let vivo = true;
    const cargar = () => api.metricas(id).then((r) => vivo && setSerie(r.metricas)).catch(() => {});
    setSerie([]); cargar();
    const t = setInterval(cargar, 5000);
    return () => { vivo = false; clearInterval(t); };
  }, [id]);

  const forzar = async (v: number | null) => {
    if (!antena) return;
    setOcupado(true);
    try { await onForzar(antena.antenaId, v); } finally { setOcupado(false); }
  };

  return (
    <AnimatePresence>
      {antena && (
        <motion.div key={antena.antenaId}
          initial={{ opacity: 0, y: 8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.97 }}
          transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}
          className="neu absolute right-4 top-4 z-10 w-[min(290px,calc(100%-32px))] origin-top-right p-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="cifra text-base font-bold">{antena.antenaId}</div>
              <div className="text-xs text-tenue">{zona?.nombre} · {zona && TIPO_ZONA[zona.tipo].etiqueta}</div>
            </div>
            <span className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
              style={{ background: `${COLOR_NEU[antena.estado]}22`, color: COLOR_NEU[antena.estado] }}>
              {ESTADO[antena.estado].etiqueta}
            </span>
            <button onClick={onCerrar} aria-label="Cerrar" className="boton-neu -mr-1 -mt-1 grid size-7 shrink-0 place-items-center text-tenue"><X className="size-3.5" /></button>
          </div>

          <div className="mt-3 flex items-baseline gap-1.5">
            {antena.gbPorMinuto === null ? <span className="text-3xl font-bold">—</span>
              : <Cifra valor={antena.gbPorMinuto} decimales={1} className="text-3xl font-bold" />}
            <span className="text-xs text-tenue">GB/min · desde {haceCuanto(antena.estadoDesde)}</span>
          </div>

          <div className="neu-hundido mt-3 px-2 pb-1 pt-2">
            <div className="mb-1 flex justify-between px-1 text-[10px] text-tenue"><span>Últimos 30 min</span><span>umbrales 60 · 129</span></div>
            <Linea datos={serie} />
          </div>

          <div className="mt-3 grid grid-cols-3 gap-2">
            {ACCIONES.map((a) => (
              <button key={a.etiqueta} disabled={ocupado} onClick={() => forzar(a.valor)}
                className="boton-neu py-2 text-[11px] font-semibold disabled:opacity-50" style={{ color: COLOR_NEU[a.estado] }}>
                {a.etiqueta}
              </button>
            ))}
          </div>
          <button disabled={ocupado || forzada === undefined} onClick={() => forzar(null)}
            className={cn("degradado mt-2 w-full rounded-xl py-2.5 text-xs font-semibold text-white transition-opacity disabled:opacity-40")}>
            {forzada === undefined ? "Funcionando sin fallas forzadas" : `Restaurar (forzada a ${forzada} GB/min)`}
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
