import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Zap } from "lucide-react";
import { api, type Antena, type Metrica, type Zona } from "../lib/api";
import { ESTADO, TIPO_ZONA } from "../lib/estados";
import { haceCuanto } from "../lib/utils";
import { NumeroAnimado } from "./NumeroAnimado";

/** Mini gráfico de la última media hora con las bandas de los umbrales. */
function Sparkline({ datos }: { datos: Metrica[] }) {
  const W = 280, H = 70, MAX = 170;
  if (datos.length < 2) return <div className="grid h-[70px] place-items-center text-xs text-tenue">Reuniendo lecturas…</div>;
  const x = (i: number) => (i / (datos.length - 1)) * W;
  const y = (v: number) => H - (Math.min(v, MAX) / MAX) * H;
  const linea = datos.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.gbPorMinuto).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-[70px] w-full overflow-visible">
      <rect x="0" y={y(129)} width={W} height={y(60) - y(129)} fill={ESTADO.NORMAL.color} opacity="0.07" />
      <line x1="0" x2={W} y1={y(129)} y2={y(129)} stroke={ESTADO.SATURADA.color} strokeDasharray="3 3" opacity="0.5" />
      <line x1="0" x2={W} y1={y(60)} y2={y(60)} stroke={ESTADO.CAIDA.color} strokeDasharray="3 3" opacity="0.5" />
      <path d={`${linea} L${W},${H} L0,${H} Z`} fill="url(#grad)" opacity="0.35" />
      <path d={linea} fill="none" stroke="var(--color-acento)" strokeWidth="1.8" />
      {datos.map((d, i) => d.estado !== "NORMAL" && (
        <circle key={i} cx={x(i)} cy={y(d.gbPorMinuto)} r="2.6" fill={ESTADO[d.estado].color} />
      ))}
      <defs>
        <linearGradient id="grad" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="var(--color-acento)" />
          <stop offset="100%" stopColor="var(--color-acento)" stopOpacity="0" />
        </linearGradient>
      </defs>
    </svg>
  );
}

const ACCIONES: { etiqueta: string; valor: number | null; estado: keyof typeof ESTADO }[] = [
  { etiqueta: "Saturar", valor: 150, estado: "SATURADA" },
  { etiqueta: "Caída", valor: 35, estado: "CAIDA" },
  { etiqueta: "Inhabilitar", valor: 0, estado: "INHABILITADA" },
  { etiqueta: "Restaurar", valor: null, estado: "NORMAL" },
];

interface Props {
  antena: Antena | null;
  zona: Zona | undefined;
  forzada: number | undefined;
  onCerrar: () => void;
  onForzar: (antenaId: string, valor: number | null) => Promise<void>;
}

export function DetalleAntena({ antena, zona, forzada, onCerrar, onForzar }: Props) {
  const [serie, setSerie] = useState<Metrica[]>([]);
  const [ocupado, setOcupado] = useState(false);
  const id = antena?.antenaId;

  useEffect(() => {
    if (!id) return;
    let vivo = true;
    const cargar = () => api.metricas(id).then((r) => vivo && setSerie(r.metricas)).catch(() => {});
    setSerie([]);
    cargar();
    const t = setInterval(cargar, 5000);
    return () => { vivo = false; clearInterval(t); };
  }, [id]);

  return (
    <AnimatePresence>
      {antena && (
        <motion.div
          key={antena.antenaId}
          initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 24 }}
          className="panel absolute right-3 top-[68px] z-10 w-[min(320px,calc(100%-24px))] p-4 shadow-2xl"
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="cifra text-lg font-semibold">{antena.antenaId}</div>
              <div className="text-xs text-tenue">{zona?.nombre} · {zona && TIPO_ZONA[zona.tipo].etiqueta}</div>
            </div>
            <button onClick={onCerrar} className="rounded-md p-1 text-tenue hover:bg-panel-2 hover:text-texto" aria-label="Cerrar">
              <X className="size-4" />
            </button>
          </div>

          <div className="mt-3 flex items-end justify-between">
            <div>
              <span
                className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold"
                style={{ background: `${ESTADO[antena.estado].color}22`, color: ESTADO[antena.estado].color }}
              >
                <span className="size-1.5 rounded-full" style={{ background: ESTADO[antena.estado].color }} />
                {ESTADO[antena.estado].etiqueta}
              </span>
              <div className="mt-1 text-[11px] text-tenue">desde {haceCuanto(antena.estadoDesde)}</div>
            </div>
            <div className="text-right">
              <div className="cifra text-3xl font-semibold leading-none">
                {antena.gbPorMinuto === null ? "—" : <NumeroAnimado valor={antena.gbPorMinuto} decimales={1} />}
              </div>
              <div className="text-[11px] text-tenue">GB/min</div>
            </div>
          </div>

          <div className="mt-3 rounded-lg bg-fondo/60 p-2">
            <div className="mb-1 flex justify-between text-[10px] uppercase tracking-wider text-tenue">
              <span>Últimos 30 min</span><span>60 · 129</span>
            </div>
            <Sparkline datos={serie} />
          </div>

          <div className="mt-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-tenue">
              <Zap className="size-3" /> Simular falla
              {forzada !== undefined && <span className="cifra ml-auto normal-case text-saturada">forzada a {forzada} GB/min</span>}
            </div>
            <div className="grid grid-cols-4 gap-1.5">
              {ACCIONES.map((a) => (
                <button
                  key={a.etiqueta}
                  disabled={ocupado}
                  onClick={async () => { setOcupado(true); try { await onForzar(antena.antenaId, a.valor); } finally { setOcupado(false); } }}
                  className="rounded-lg border border-borde px-1 py-1.5 text-[11px] font-medium transition hover:brightness-125 disabled:opacity-50"
                  style={{ color: ESTADO[a.estado].color, background: `${ESTADO[a.estado].color}12` }}
                >
                  {a.etiqueta}
                </button>
              ))}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
