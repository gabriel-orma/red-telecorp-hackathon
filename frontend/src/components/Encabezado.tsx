import { useEffect, useState } from "react";
import { Radio, WifiOff } from "lucide-react";
import { cn, haceCuanto, horaLima } from "../lib/utils";

export function Encabezado({ ultimaCarga, error }: { ultimaCarga: number | null; error: string | null }) {
  const [ahora, setAhora] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setAhora(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const enVivo = !error && ultimaCarga !== null && ahora - ultimaCarga < 10_000;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-borde bg-panel/80 px-4 backdrop-blur md:px-6">
      <div className="flex items-center gap-3">
        <div className="grid size-9 place-items-center rounded-xl bg-acento/10 ring-1 ring-acento/30">
          <Radio className="size-5 text-acento" />
        </div>
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-tight">Red TeleCorp</div>
          <div className="text-[11px] uppercase tracking-[0.14em] text-tenue">Centro de Control de Red</div>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div
          className={cn(
            "flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1",
            enVivo ? "bg-normal/10 text-normal ring-normal/30" : "bg-caida/10 text-caida ring-caida/30",
          )}
          title={error ?? undefined}
        >
          {enVivo ? <span className="latido size-2 rounded-full bg-normal" /> : <WifiOff className="size-3.5" />}
          {enVivo ? "EN VIVO" : "SIN CONEXIÓN"}
          <span className="hidden text-tenue sm:inline">· {haceCuanto(ultimaCarga ? new Date(ultimaCarga).toISOString() : null, ahora)}</span>
        </div>
        <div className="cifra hidden text-sm text-tenue md:block">
          Lima <span className="text-texto">{horaLima(new Date(ahora))}</span>
        </div>
      </div>
    </header>
  );
}
