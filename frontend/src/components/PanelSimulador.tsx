import { useState } from "react";
import { FlaskConical, Loader2, RotateCcw } from "lucide-react";
import type { EstadoSimulador } from "../lib/api";
import { cn } from "../lib/utils";

interface Props {
  estado: EstadoSimulador | null;
  onCambiar: (cambios: { activo?: boolean; limpiarFallas?: boolean }) => Promise<void>;
}

export function PanelSimulador({ estado, onCambiar }: Props) {
  const [ocupado, setOcupado] = useState(false);
  const fallas = estado ? Object.keys(estado.fallas).length : 0;
  const ejecutar = async (c: { activo?: boolean; limpiarFallas?: boolean }) => {
    setOcupado(true);
    try { await onCambiar(c); } finally { setOcupado(false); }
  };

  return (
    <div className="panel absolute left-3 top-3 z-10 flex items-center gap-3 px-3 py-2">
      <FlaskConical className="size-4 text-acento" />
      <div className="leading-tight">
        <div className="text-xs font-semibold">Simulador de antenas</div>
        <div className="text-[10px] text-tenue">
          {estado?.activo ? `${estado.muestrasPorMinuto} lecturas/min` : "apagado · costo $0"}
          {fallas > 0 && <span className="text-saturada"> · {fallas} falla{fallas > 1 ? "s" : ""} forzada{fallas > 1 ? "s" : ""}</span>}
        </div>
      </div>

      <button
        role="switch"
        aria-checked={!!estado?.activo}
        disabled={!estado || ocupado}
        onClick={() => ejecutar({ activo: !estado?.activo })}
        className={cn(
          "relative h-6 w-11 rounded-full transition disabled:opacity-50",
          estado?.activo ? "bg-normal/80 shadow-[0_0_12px_#22c55e80]" : "bg-borde",
        )}
        title={estado?.activo ? "Apagar simulador" : "Encender simulador"}
      >
        <span className={cn("absolute top-0.5 grid size-5 place-items-center rounded-full bg-white transition-all", estado?.activo ? "left-[22px]" : "left-0.5")}>
          {ocupado && <Loader2 className="size-3 animate-spin text-fondo" />}
        </span>
      </button>

      {fallas > 0 && (
        <button
          disabled={ocupado}
          onClick={() => ejecutar({ limpiarFallas: true })}
          className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-tenue transition hover:bg-panel-2 hover:text-texto"
          title="Quitar todas las fallas forzadas"
        >
          <RotateCcw className="size-3" /> Restaurar todo
        </button>
      )}
    </div>
  );
}
