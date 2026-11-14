import { useEffect, useState } from "react";
import { ListChecks, Map, Radio, Siren, Smartphone, WifiOff } from "lucide-react";
import { enlace, useRuta } from "../lib/router";
import { cn, haceCuanto, horaLima } from "../lib/utils";

const SECCIONES = [
  { ruta: "/", etiqueta: "Mapa en vivo", icono: Map },
  { ruta: "/incidencias", etiqueta: "Incidencias", icono: ListChecks },
  { ruta: "/colectivos", etiqueta: "Colectivos", icono: Siren },
  { ruta: "/portal", etiqueta: "Portal usuario", icono: Smartphone },
];

export function Encabezado({ ultimaCarga, error, colectivosActivos = 0 }: { ultimaCarga: number | null; error: string | null; colectivosActivos?: number }) {
  const ruta = useRuta().split("?")[0];
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

      <nav className="flex items-center gap-1 rounded-xl bg-fondo/60 p-1 ring-1 ring-borde">
        {SECCIONES.map(({ ruta: r, etiqueta, icono: Icono }) => (
          <a
            key={r}
            {...enlace(r)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
              ruta === r ? "bg-panel-2 text-texto ring-1 ring-borde" : "text-tenue hover:text-texto",
            )}
            title={etiqueta}
          >
            <Icono className={cn("size-3.5", r === "/colectivos" && colectivosActivos > 0 && "text-caida")} />
            <span className="hidden lg:inline">{etiqueta}</span>
            {r === "/colectivos" && colectivosActivos > 0 && (
              <span className="cifra latido grid min-w-4 place-items-center rounded-full bg-caida px-1 text-[10px] font-bold text-white">{colectivosActivos}</span>
            )}
          </a>
        ))}
      </nav>

      <div className="flex items-center gap-4">
        <div
          className={cn(
            "flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1",
            enVivo ? "bg-normal/10 text-normal ring-normal/30" : "bg-caida/10 text-caida ring-caida/30",
          )}
          title={error ?? undefined}
        >
          {enVivo ? <span className="latido size-2 rounded-full bg-normal" /> : <WifiOff className="size-3.5" />}
          <span className="hidden sm:inline">{enVivo ? "EN VIVO" : "SIN CONEXIÓN"}</span>
          <span className="hidden text-tenue sm:inline">· {haceCuanto(ultimaCarga ? new Date(ultimaCarga).toISOString() : null, ahora)}</span>
        </div>
        <div className="cifra hidden text-sm text-tenue md:block">
          Lima <span className="text-texto">{horaLima(new Date(ahora))}</span>
        </div>
      </div>
    </header>
  );
}
