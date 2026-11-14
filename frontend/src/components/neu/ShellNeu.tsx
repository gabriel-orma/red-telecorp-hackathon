import { useEffect, useState, type ReactNode } from "react";
import { ChartArea, ListChecks, Map, Search, Siren, Smartphone } from "lucide-react";
import { enlace, useRuta } from "../../lib/router";
import { cn, horaLima } from "../../lib/utils";

const SECCIONES = [
  { ruta: "/", etiqueta: "Mapa en vivo", icono: Map },
  { ruta: "/incidencias", etiqueta: "Incidencias", icono: ListChecks },
  { ruta: "/colectivos", etiqueta: "Colectivos", icono: Siren },
  { ruta: "/portal", etiqueta: "Estado público", icono: ChartArea },
  { ruta: "/portal/reportar", etiqueta: "Portal usuario", icono: Smartphone },
];

interface Props {
  titulo: string;
  enVivo: boolean;
  colectivosActivos: number;
  onBuscar: () => void;
  acciones?: ReactNode;
  children: ReactNode;
}

/** Marco del panel del operador en el estilo neumórfico: barra lateral de íconos + barra superior. */
export function ShellNeu({ titulo, enVivo, colectivosActivos, onBuscar, acciones, children }: Props) {
  const ruta = useRuta().split("?")[0];
  const [ahora, setAhora] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setAhora(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const nav = SECCIONES.map(({ ruta: r, etiqueta, icono: Icono }) => (
    <a key={r} {...enlace(r)} title={etiqueta} aria-label={etiqueta} data-activo={ruta === r}
      className={cn("boton-neu relative grid size-11 place-items-center text-tenue", ruta === r && "text-acento")}>
      <Icono className="size-[18px]" />
      {r === "/colectivos" && colectivosActivos > 0 && (
        <span className="degradado absolute -right-1 -top-1 grid min-w-[18px] place-items-center rounded-full px-1 text-[10px] font-bold text-white">
          {colectivosActivos}
        </span>
      )}
    </a>
  ));

  return (
    <div className="tema-neu flex h-full gap-5 p-3 md:p-5">
      {/* Barra lateral (escritorio) */}
      <aside className="neu hidden w-[68px] shrink-0 flex-col items-center gap-3 py-4 md:flex">
        <div className="degradado mb-3 grid size-10 place-items-center rounded-2xl text-sm font-bold text-white">TC</div>
        {nav}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col gap-5 pb-16 md:pb-0">
        {/* Barra superior */}
        <header className="flex flex-wrap items-center gap-3">
          <div className="mr-auto">
            <h1 className="text-xl font-bold tracking-tight">{titulo}</h1>
            <div className="flex items-center gap-2 text-xs text-tenue">
              <span className={cn("size-2 rounded-full", enVivo ? "latido bg-normal" : "bg-caida")} />
              {enVivo ? "En vivo" : "Sin conexión"} · Lima <span className="cifra text-texto">{horaLima(ahora)}</span>
            </div>
          </div>
          <button onClick={onBuscar}
            className="neu-hundido flex h-11 w-full items-center gap-2 px-4 text-sm text-tenue sm:w-72">
            <Search className="size-4" /> Buscar antena o zona…
            <kbd className="ml-auto rounded-md border border-borde px-1.5 text-[10px]">Ctrl K</kbd>
          </button>
          {acciones}
        </header>
        {children}
      </div>

      {/* Navegación inferior (celular) */}
      <nav className="neu fixed inset-x-3 bottom-3 z-30 flex justify-around px-2 py-2 md:hidden">{nav}</nav>
    </div>
  );
}
