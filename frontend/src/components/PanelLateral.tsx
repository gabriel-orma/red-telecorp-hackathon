import { motion } from "framer-motion";
import { Activity, Flame, Users } from "lucide-react";
import type { Antena, EstadoAntena, Zona } from "../lib/api";
import { ESTADO, GRAVEDAD, ORDEN_ESTADOS, TIPO_ZONA } from "../lib/estados";
import { cn, numero } from "../lib/utils";
import { NumeroAnimado } from "./NumeroAnimado";

function AnilloOperativas({ operativas, total }: { operativas: number; total: number }) {
  const r = 34;
  const c = 2 * Math.PI * r;
  const p = total ? operativas / total : 0;
  const color = p === 1 ? ESTADO.NORMAL.color : p > 0.85 ? ESTADO.SATURADA.color : ESTADO.CAIDA.color;
  return (
    <svg viewBox="0 0 84 84" className="size-[84px] -rotate-90">
      <circle cx="42" cy="42" r={r} fill="none" stroke="var(--color-borde)" strokeWidth="7" />
      <motion.circle
        cx="42" cy="42" r={r} fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={c} animate={{ strokeDashoffset: c * (1 - p) }} transition={{ duration: 0.8, ease: "easeOut" }}
        style={{ filter: `drop-shadow(0 0 6px ${color}80)` }}
      />
    </svg>
  );
}

interface Props {
  antenas: Antena[];
  zonas: Zona[];
  onZona: (z: Zona) => void;
  reportes24h: number;
}

export function PanelLateral({ antenas, zonas, onZona, reportes24h }: Props) {
  const conteo = (e: EstadoAntena) => antenas.filter((a) => a.estado === e).length;
  const operativas = conteo("NORMAL") + conteo("SATURADA");
  const trafico = antenas.reduce((s, a) => s + (a.gbPorMinuto ?? 0), 0);
  const clientesEnRiesgo = zonas
    .filter((z) => GRAVEDAD[z.estado] >= GRAVEDAD.CAIDA)
    .reduce((s, z) => s + z.clientesEstimados, 0);
  const ordenadas = [...zonas].sort(
    (a, b) => GRAVEDAD[b.estado] - GRAVEDAD[a.estado] || b.criticidad - a.criticidad,
  );

  return (
    <aside className="scroll-fino flex min-h-0 w-full flex-1 flex-col gap-3 overflow-y-auto p-3 md:w-[340px] md:flex-none">
      {/* KPI principal */}
      <section className="panel flex items-center gap-4 p-4">
        <div className="relative">
          <AnilloOperativas operativas={operativas} total={antenas.length} />
          <div className="absolute inset-0 grid place-items-center">
            <span className="cifra text-lg font-semibold">
              <NumeroAnimado valor={operativas} />
              <span className="text-xs text-tenue">/{antenas.length}</span>
            </span>
          </div>
        </div>
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-tenue">Antenas operativas</div>
          <div className="mt-1 flex items-baseline gap-1.5">
            <Activity className="size-4 self-center text-acento" />
            <span className="cifra text-2xl font-semibold"><NumeroAnimado valor={trafico} /></span>
            <span className="text-xs text-tenue">GB/min</span>
          </div>
          <div className={cn("mt-1 flex items-center gap-1.5 text-xs", clientesEnRiesgo ? "text-caida" : "text-tenue")}>
            <Users className="size-3.5" />
            <span className="cifra"><NumeroAnimado valor={clientesEnRiesgo} /></span> clientes en zonas con falla
          </div>
          <div className="mt-0.5 flex items-center gap-1.5 text-xs text-[#fb923c]">
            <Flame className="size-3.5" />
            <span className="cifra"><NumeroAnimado valor={reportes24h} /></span> reportes de usuarios (24 h)
          </div>
        </div>
      </section>

      {/* Conteo por estado */}
      <section className="grid grid-cols-2 gap-2">
        {ORDEN_ESTADOS.map((e) => (
          <div key={e} className="panel relative overflow-hidden px-3 py-2.5">
            <div className="absolute inset-y-0 left-0 w-1" style={{ background: ESTADO[e].color }} />
            <div className="text-[11px] uppercase tracking-wider text-tenue">{ESTADO[e].etiqueta}</div>
            <div className="flex items-baseline justify-between">
              <span className="cifra text-2xl font-semibold" style={{ color: conteo(e) && e !== "NORMAL" ? ESTADO[e].color : undefined }}>
                <NumeroAnimado valor={conteo(e)} />
              </span>
              <span className="cifra text-[10px] text-tenue">{ESTADO[e].rango}</span>
            </div>
          </div>
        ))}
      </section>

      {/* Zonas */}
      <section className="panel p-2">
        <div className="flex items-center justify-between px-2 pb-2 pt-1">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-tenue">Zonas · {zonas.length}</h2>
          <span className="text-[10px] text-tenue">ordenadas por gravedad</span>
        </div>
        <ul className="flex flex-col gap-1">
          {ordenadas.map((z) => {
            const Icono = TIPO_ZONA[z.tipo].icono;
            const color = ESTADO[z.estado].color;
            return (
              <motion.li key={z.zonaId} layout transition={{ type: "spring", stiffness: 500, damping: 40 }}>
                <button
                  onClick={() => onZona(z)}
                  className="group flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition hover:bg-panel-2"
                >
                  <div className="grid size-8 shrink-0 place-items-center rounded-lg" style={{ background: `${color}1a`, color }}>
                    <Icono className="size-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{z.nombre}</div>
                    <div className="text-[11px] text-tenue">
                      {TIPO_ZONA[z.tipo].etiqueta} · {numero(z.clientesEstimados)} clientes
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[11px] font-semibold" style={{ color }}>{ESTADO[z.estado].etiqueta}</div>
                    <div className="cifra text-[11px] text-tenue">{numero(Math.round(z.traficoGbPorMinuto))} GB/m</div>
                  </div>
                </button>
              </motion.li>
            );
          })}
        </ul>
      </section>
    </aside>
  );
}
