import { motion } from "framer-motion";
import { Check, Mail, Megaphone, Smartphone, type LucideIcon } from "lucide-react";
import type { CanalAviso, EstadoIncidencia, EventoHistorial } from "../lib/api";
import { ESTADO_INCIDENCIA, EVENTO, ORDEN_INCIDENCIA } from "../lib/estados";
import { cn, haceCuanto } from "../lib/utils";

const fecha = (iso: string) =>
  new Date(iso).toLocaleString("es-PE", { timeZone: "America/Lima", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });

/** Progreso tipo "pedido en camino": los 5 estados con el actual resaltado. */
export function Progreso({ estado, compacto = false }: { estado: EstadoIncidencia; compacto?: boolean }) {
  const idx = ORDEN_INCIDENCIA.indexOf(estado);
  return (
    <ol className="relative flex items-start justify-between">
      <div className="absolute left-4 right-4 top-4 h-0.5 bg-borde" />
      <motion.div
        className="absolute left-4 top-4 h-0.5"
        style={{ background: ESTADO_INCIDENCIA[estado].color }}
        initial={{ width: 0 }}
        animate={{ width: `calc((100% - 2rem) * ${idx / (ORDEN_INCIDENCIA.length - 1)})` }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      />
      {ORDEN_INCIDENCIA.map((e, i) => {
        const { etiqueta, color, icono: Icono } = ESTADO_INCIDENCIA[e];
        const hecho = i < idx, actual = i === idx;
        return (
          <li key={e} className="relative z-10 flex w-16 flex-col items-center gap-1.5 text-center">
            <motion.div
              className={cn("grid size-8 place-items-center rounded-full ring-2", !hecho && !actual && "bg-panel ring-borde text-tenue")}
              style={hecho || actual ? { background: actual ? color : `${color}33`, color: actual ? "#16161a" : color, boxShadow: actual ? `0 0 18px ${color}99` : undefined, ["--tw-ring-color" as string]: color } : undefined}
              animate={actual ? { scale: [1, 1.12, 1] } : {}}
              transition={actual ? { repeat: Infinity, duration: 2 } : {}}
            >
              {hecho ? <Check className="size-4" /> : <Icono className="size-4" />}
            </motion.div>
            {!compacto && (
              <span className={cn("text-[10px] leading-tight", actual ? "font-semibold text-texto" : "text-tenue")}>{etiqueta}</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/** Historial inmutable en orden cronológico inverso. */
export function Historial({ eventos }: { eventos: EventoHistorial[] }) {
  const orden = [...eventos].sort((a, b) => b.ocurridoEn.localeCompare(a.ocurridoEn));
  return (
    <ul className="relative space-y-3 border-l border-borde pl-4">
      {orden.map((e, i) => {
        if (e.tipoEvento === "NOTIFICACION_ENVIADA") return <Aviso key={e.ocurridoEn + i} e={e} />;
        const Icono = EVENTO[e.tipoEvento]?.icono ?? EVENTO.CAMBIO_ESTADO.icono;
        const estado = e.estadoNuevo as EstadoIncidencia | null;
        const color = estado && ESTADO_INCIDENCIA[estado] ? ESTADO_INCIDENCIA[estado].color : "#8b8b97";
        return (
          <motion.li key={e.ocurridoEn + i} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="relative">
            <span className="absolute -left-[25px] top-0.5 grid size-[17px] place-items-center rounded-full ring-4 ring-panel" style={{ background: color }}>
              <Icono className="size-2.5 text-fondo" />
            </span>
            <div className="text-sm">
              {e.tipoEvento === "CAMBIO_ESTADO" && estado
                ? <>Pasó a <b style={{ color }}>{ESTADO_INCIDENCIA[estado]?.etiqueta ?? estado}</b></>
                : EVENTO[e.tipoEvento]?.etiqueta ?? e.tipoEvento}
            </div>
            {e.detalle && <div className="text-xs text-tenue">{e.detalle}</div>}
            <div className="cifra text-[10px] text-tenue">{fecha(e.ocurridoEn)} · {haceCuanto(e.ocurridoEn)} · {e.actor.toLowerCase()}</div>
          </motion.li>
        );
      })}
    </ul>
  );
}

const CANAL: Record<CanalAviso, { texto: string; icono: LucideIcon }> = {
  AZURE_EMAIL: { texto: "Te avisamos por correo · Azure", icono: Mail },
  SNS_EMAIL: { texto: "Te avisamos por correo · AWS", icono: Mail },
  APP: { texto: "Aviso en la app", icono: Smartphone },
};
const esCanalConocido = (c: string): c is CanalAviso => c in CANAL;

/** Aviso enviado al usuario (detalle JSON con asunto, mensaje y canales). */
function Aviso({ e }: { e: EventoHistorial }) {
  let d: { asunto?: string; mensaje?: string; canales?: Record<string, string>; canal?: string } = {};
  try { d = JSON.parse(e.detalle); } catch { d = { mensaje: e.detalle }; }
  // El canal puede venir en el evento o dentro del detalle; solo se muestran los conocidos (nunca direcciones ni ids).
  const candidatos = [e.canal, d.canal, ...Object.keys(d.canales ?? {})].map((c) => c?.toUpperCase()).filter((c): c is string => !!c);
  const conocidos = [...new Set(candidatos.filter(esCanalConocido))];
  const otros = Object.entries(d.canales ?? {}).filter(([canal]) => !esCanalConocido(canal.toUpperCase()));
  return (
    <motion.li initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} className="relative">
      <span className="absolute -left-[25px] top-0.5 grid size-[17px] place-items-center rounded-full bg-acento ring-4 ring-panel">
        <Megaphone className="size-2.5 text-fondo" />
      </span>
      <div className="rounded-xl rounded-tl-sm bg-acento/10 px-3 py-2 ring-1 ring-acento/25">
        <div className="text-xs font-semibold text-acento">{d.asunto ?? "Aviso"}</div>
        <div className="mt-0.5 text-xs text-texto/90">{d.mensaje}</div>
        {(conocidos.length > 0 || otros.length > 0) && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {conocidos.map((c) => {
              const { texto, icono: Icono } = CANAL[c];
              return (
                <span key={c} className="inline-flex items-center gap-1 rounded-full bg-fondo/70 px-2 py-0.5 text-[10px] font-medium text-texto ring-1 ring-acento/40">
                  <Icono className="size-3 text-acento" aria-hidden />{texto}
                </span>
              );
            })}
            {otros.map(([canal, r]) => (
              <span key={canal} className="cifra rounded bg-fondo/60 px-1.5 text-[9px] uppercase text-tenue" title={r}>{canal}</span>
            ))}
          </div>
        )}
      </div>
      <div className="cifra mt-0.5 text-[10px] text-tenue">{fecha(e.ocurridoEn)} · {haceCuanto(e.ocurridoEn)}</div>
    </motion.li>
  );
}

export function ChipEstado({ estado }: { estado: EstadoIncidencia }) {
  const { etiqueta, color } = ESTADO_INCIDENCIA[estado];
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ background: `${color}22`, color }}>
      <span className="size-1.5 rounded-full" style={{ background: color }} />
      {etiqueta}
    </span>
  );
}
