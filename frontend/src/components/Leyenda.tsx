import { Flame } from "lucide-react";
import { ESTADO, ORDEN_ESTADOS } from "../lib/estados";
import { cn } from "../lib/utils";

interface Props {
  verCalor: boolean;
  onVerCalor: (v: boolean) => void;
  reportes: number;
}

export function Leyenda({ verCalor, onVerCalor, reportes }: Props) {
  return (
    <div className="panel absolute bottom-3 left-3 right-14 z-10 flex flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 text-[11px] md:right-auto">
      {ORDEN_ESTADOS.map((e) => (
        <span key={e} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full" style={{ background: ESTADO[e].color, boxShadow: `0 0 8px ${ESTADO[e].color}` }} />
          <span>{ESTADO[e].etiqueta}</span>
          <span className="cifra hidden text-tenue sm:inline">{ESTADO[e].rango}</span>
        </span>
      ))}
      <button
        onClick={() => onVerCalor(!verCalor)}
        className={cn(
          "flex items-center gap-1.5 rounded-md px-2 py-0.5 ring-1 transition",
          verCalor ? "bg-[#f97316]/15 text-[#fb923c] ring-[#f97316]/40" : "text-tenue ring-borde hover:text-texto",
        )}
        title="Mostrar u ocultar el mapa de calor de reportes de usuarios (24 h)"
      >
        <Flame className="size-3" /> Reportes 24 h <span className="cifra">{reportes}</span>
      </button>
    </div>
  );
}
