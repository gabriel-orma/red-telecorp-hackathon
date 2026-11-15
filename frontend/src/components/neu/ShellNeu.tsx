import { useEffect, useState, type ReactNode } from "react";
import { BarChart3, ChartArea, Cloud, Contrast, Film, ListChecks, Map, Maximize2, Minimize2, Search, Siren, Smartphone } from "lucide-react";
import { useConexionTiempoReal } from "../../lib/tiempoReal";
import { enlace, useRuta } from "../../lib/router";
import { cn, horaLima } from "../../lib/utils";

const SECCIONES = [
  { ruta: "/", etiqueta: "Mapa en vivo", icono: Map },
  { ruta: "/linea-tiempo", etiqueta: "Línea de tiempo", icono: Film },
  { ruta: "/incidencias", etiqueta: "Incidencias", icono: ListChecks },
  { ruta: "/colectivos", etiqueta: "Colectivos", icono: Siren },
  { ruta: "/analitica", etiqueta: "Analítica", icono: BarChart3 },
  { ruta: "/nubes", etiqueta: "Nubes conectadas", icono: Cloud },
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
  const tiempoReal = useConexionTiempoReal();
  const [sala, setSala] = usePreferencia("modo-sala");
  const [contraste, setContraste] = usePreferencia("alto-contraste");
  const [ahora, setAhora] = useState(() => new Date());
  // Título de pestaña por sección (lectores de pantalla y pestañas múltiples): «Sección · Red TeleCorp».
  useEffect(() => { document.title = `${titulo} · Red TeleCorp`; }, [titulo]);
  useEffect(() => {
    const t = setInterval(() => setAhora(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const nav = SECCIONES.map(({ ruta: r, etiqueta, icono: Icono }) => (
    <a key={r} {...enlace(r)} title={etiqueta} aria-label={etiqueta} aria-current={ruta === r ? "page" : undefined} data-activo={ruta === r}
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
      <aside className="neu ocultar-en-sala hidden w-[68px] shrink-0 flex-col items-center gap-3 py-4 md:flex">
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
              {enVivo ? (tiempoReal ? "En vivo · WebSocket" : "En vivo · polling") : "Sin conexión"} · Lima <span className="cifra text-texto">{horaLima(ahora)}</span>
            </div>
          </div>
          <button onClick={onBuscar}
            className="neu-hundido flex h-11 w-full items-center gap-2 px-4 text-sm text-tenue sm:w-72">
            <Search className="size-4" /> Buscar antena o zona…
            <kbd className="ml-auto rounded-md border border-borde px-1.5 text-[10px]">Ctrl K</kbd>
          </button>
          {acciones}
          <button onClick={() => setContraste(!contraste)} data-activo={contraste} title="Alto contraste" aria-label="Alto contraste"
            className={cn("boton-neu hidden size-11 place-items-center md:grid", contraste ? "text-acento" : "text-tenue")}><Contrast className="size-4" /></button>
          <button onClick={() => alternarSala(!sala, setSala)} data-activo={sala} title={sala ? "Salir del modo sala" : "Modo sala (pantalla completa)"}
            aria-label="Modo sala" className={cn("boton-neu hidden size-11 place-items-center md:grid", sala ? "text-acento" : "text-tenue")}>
            {sala ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
          </button>
        </header>
        {children}
      </div>

      {/* Navegación inferior (celular) */}
      <nav className="neu fixed inset-x-3 bottom-3 z-30 flex justify-around px-2 py-2 md:hidden">{nav}</nav>
    </div>
  );
}

/** Preferencia de la interfaz guardada en el navegador y reflejada como clase en <html>. */
function usePreferencia(clase: string): [boolean, (v: boolean) => void] {
  const [valor, setValor] = useState(() => { try { return localStorage.getItem(`telecorp.${clase}`) === "1"; } catch { return false; } });
  useEffect(() => {
    document.documentElement.classList.toggle(clase, valor);
    try { localStorage.setItem(`telecorp.${clase}`, valor ? "1" : "0"); } catch { /* sin almacenamiento */ }
  }, [clase, valor]);
  return [valor, setValor];
}

/** Modo sala de operaciones: pantalla completa y solo el mapa con los indicadores clave. */
function alternarSala(activar: boolean, setSala: (v: boolean) => void) {
  setSala(activar);
  try {
    if (activar && !document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {});
    if (!activar && document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
  } catch { /* el navegador no permite pantalla completa */ }
}
