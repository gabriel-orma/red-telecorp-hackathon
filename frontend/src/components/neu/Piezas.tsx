import NumberFlow from "@number-flow/react";
import { motion } from "framer-motion";
import { Check, FlaskConical } from "lucide-react";
import type { Colectivo } from "../../lib/api";
import { cn } from "../../lib/utils";
import { ETAPAS, etapaDe } from "./paleta";

/** Cifra que anima sus dígitos al cambiar (NumberFlow). */
export function Cifra({ valor, decimales = 0, className }: { valor: number; decimales?: number; className?: string }) {
  return (
    <NumberFlow value={valor} className={cn("cifra", className)} locales="es-PE"
      format={{ minimumFractionDigits: decimales, maximumFractionDigits: decimales }} />
  );
}

/** Etiqueta de dato simulado: icono + texto (no depende del color). Lo simulado nunca se confunde con lo operativo. */
export function ChipSimulado({ className }: { className?: string }) {
  return (
    <span title="Nace de una simulación (escenario de demo, falla forzada o vecinos ficticios). No cuenta como dato operativo."
      className={cn("inline-flex shrink-0 items-center gap-1 rounded-full bg-acento/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-acento ring-1 ring-acento/40", className)}>
      <FlaskConical className="size-3" aria-hidden="true" /> Simulado
    </span>
  );
}

/** Anillo con degradado violeta → rosa (estilo de la referencia). */
export function Anillo({ proporcion, tamano = 132, grosor = 12, children }: { proporcion: number; tamano?: number; grosor?: number; children?: React.ReactNode }) {
  const r = (tamano - grosor) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative" style={{ width: tamano, height: tamano }}>
      <svg viewBox={`0 0 ${tamano} ${tamano}`} className="-rotate-90" width={tamano} height={tamano}>
        <defs>
          <linearGradient id="anillo-neu" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#7c5cff" /><stop offset="100%" stopColor="#e05ab0" />
          </linearGradient>
        </defs>
        <circle cx={tamano / 2} cy={tamano / 2} r={r} fill="none" stroke="#26262c" strokeWidth={grosor} />
        <motion.circle cx={tamano / 2} cy={tamano / 2} r={r} fill="none" stroke="url(#anillo-neu)" strokeWidth={grosor}
          strokeLinecap="round" strokeDasharray={c} initial={false}
          animate={{ strokeDashoffset: c * (1 - Math.min(1, Math.max(0, proporcion))) }}
          transition={{ type: "spring", stiffness: 120, damping: 22 }} />
      </svg>
      <div className="neu-hundido absolute grid place-items-center"
        style={{ inset: grosor + 6, borderRadius: "50%" }}>{children}</div>
    </div>
  );
}

/** Interruptor con degradado cuando está encendido. */
export function Interruptor({ activo, onClick, deshabilitado, etiqueta }: { activo: boolean; onClick: () => void; deshabilitado?: boolean; etiqueta: string }) {
  return (
    <button role="switch" aria-checked={activo} aria-label={etiqueta} disabled={deshabilitado} onClick={onClick}
      className={cn("relative h-7 w-12 shrink-0 rounded-full transition-[background] disabled:opacity-50",
        activo ? "degradado" : "neu-hundido")}>
      <motion.span className="absolute top-1 size-5 rounded-full bg-white shadow"
        initial={false} animate={{ left: activo ? 24 : 4 }} transition={{ type: "spring", stiffness: 500, damping: 32 }} />
    </button>
  );
}

/** Pasos del incidente colectivo agrupados en 4 etapas (Detectado → Verificado → Monitoreando → Restablecido). */
export function PasosColectivo({ colectivo }: { colectivo: Colectivo }) {
  const actual = colectivo.pasoActual === "CERRADO" ? ETAPAS.length : etapaDe(colectivo.pasoActual);
  return (
    <ol className="flex items-center gap-2">
      {ETAPAS.map((e, i) => {
        const hecho = i < actual, enCurso = i === actual;
        return (
          <li key={e.etiqueta} className={cn("flex items-center gap-2", i < ETAPAS.length - 1 && "flex-1")}>
            <span className={cn("grid size-8 shrink-0 place-items-center rounded-full text-xs font-bold",
              hecho && "bg-normal/15 text-normal", enCurso && "degradado text-white shadow-[0_0_18px_#e05ab055]",
              !hecho && !enCurso && "neu-hundido text-tenue")}>
              {hecho ? <Check className="size-4" /> : i + 1}
            </span>
            <span className={cn("hidden text-xs leading-tight lg:block", enCurso ? "font-semibold text-texto" : "text-tenue")}>
              {e.etiqueta}
              <span className="block text-[10px] font-normal text-tenue">{hecho ? "Completado" : enCurso ? "En curso" : "Pendiente"}</span>
            </span>
            {i < ETAPAS.length - 1 && <span className={cn("h-px min-w-4 flex-1", hecho ? "bg-normal/40" : "bg-borde")} />}
          </li>
        );
      })}
    </ol>
  );
}
