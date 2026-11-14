import { motion } from "framer-motion";
import { Check, Loader2, Repeat } from "lucide-react";
import type { Colectivo } from "../lib/api";
import { PASOS_FLUJO } from "../lib/estados";
import { cn } from "../lib/utils";

/**
 * Diagrama del flujo de Step Functions con el paso actual resaltado.
 * El backend actualiza `pasoActual` en cada Lambda del flujo; aquí solo se pinta.
 */
export function FlujoColectivo({ colectivo }: { colectivo: Colectivo }) {
  const actual = PASOS_FLUJO.findIndex((p) => p.paso === colectivo.pasoActual);
  const terminado = colectivo.pasoActual === "CERRADO";
  const critico = colectivo.prioridad === "CRITICA";

  return (
    <ol className="relative space-y-1">
      {PASOS_FLUJO.map((p, i) => {
        // La alerta al NOC solo ocurre si el Choice decide "crítico".
        const omitido = p.paso === "ALERTAR_OPERADOR" && !critico && i < actual;
        const hecho = (i < actual || terminado) && !omitido;
        const enCurso = i === actual && !terminado;
        const Icono = p.icono;
        return (
          <motion.li
            key={p.paso}
            initial={false}
            animate={{ opacity: hecho || enCurso ? 1 : 0.45 }}
            className={cn(
              "relative flex items-center gap-3 rounded-lg px-2.5 py-1.5",
              enCurso && "bg-acento/10 ring-1 ring-acento/50 shadow-[0_0_20px_#a78bfa22]",
            )}
          >
            {i < PASOS_FLUJO.length - 1 && (
              <span className={cn("absolute left-[22px] top-8 h-3 w-px", hecho ? "bg-acento/60" : "bg-borde")} />
            )}
            <span
              className={cn(
                "grid size-6 shrink-0 place-items-center rounded-full ring-1",
                hecho && "bg-acento/20 text-acento ring-acento/40",
                enCurso && "bg-acento text-fondo ring-acento",
                !hecho && !enCurso && "bg-panel text-tenue ring-borde",
              )}
            >
              {hecho ? <Check className="size-3.5" /> : enCurso && p.tipo === "loop" ? <Repeat className="size-3.5 animate-spin [animation-duration:3s]" />
                : enCurso ? <Loader2 className="size-3.5 animate-spin" /> : <Icono className="size-3.5" />}
            </span>
            <div className="min-w-0 flex-1">
              <div className={cn("flex items-center gap-1.5 text-xs", enCurso ? "font-semibold text-texto" : "text-texto/90")}>
                {p.etiqueta}
                {p.tipo && (
                  <span className="cifra rounded bg-panel-2 px-1 text-[9px] text-tenue">
                    {p.tipo === "map" ? "Map" : p.tipo === "choice" ? "Choice" : "Wait"}
                  </span>
                )}
                {omitido && <span className="text-[10px] text-tenue">(no crítico)</span>}
              </div>
              <div className="truncate text-[10px] text-tenue">{p.detalle}</div>
            </div>
          </motion.li>
        );
      })}
    </ol>
  );
}

/** Versión mínima: barra de progreso del flujo para tarjetas. */
export function FlujoMini({ colectivo }: { colectivo: Colectivo }) {
  const actual = PASOS_FLUJO.findIndex((p) => p.paso === colectivo.pasoActual);
  return (
    <div className="flex gap-0.5">
      {PASOS_FLUJO.map((p, i) => (
        <span
          key={p.paso}
          className={cn("h-1 flex-1 rounded-full", i < actual || colectivo.pasoActual === "CERRADO" ? "bg-acento" : i === actual ? "latido bg-acento" : "bg-borde")}
        />
      ))}
    </div>
  );
}
