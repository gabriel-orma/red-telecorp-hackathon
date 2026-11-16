import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  BarChart3, ChartArea, ChevronRight, Cloud, Film, Flame, ListChecks, ListOrdered, Map, Radio, Siren, Smartphone,
  TowerControl, Users, Zap, type LucideIcon,
} from "lucide-react";
import { apiEscenarios, apiPortal, type Antena, type Colectivo, type EstadoEscenario, type EstadoRed, type Zona } from "../lib/api";
import { ESTADO, ESTADO_COLECTIVO, GRAVEDAD, NIVEL_RED, PRIORIDAD, TIPO_ZONA } from "../lib/estados";
import { usePolling } from "../hooks/usePolling";
import { useAlCambiar } from "../lib/tiempoReal";
import { enlace, navegar } from "../lib/router";
import { cn, haceCuanto, numero } from "../lib/utils";
import { ShellNeu } from "../components/neu/ShellNeu";
import { PaletaComandos } from "../components/neu/PaletaComandos";
import { Anillo, Cifra } from "../components/neu/Piezas";
import { COLOR_NEU } from "../components/neu/paleta";
import { GraficoReportes } from "../components/GraficoReportes";

interface Props { antenas: Antena[]; zonas: Zona[]; colectivos: Colectivo[]; enVivo: boolean }

/** Accesos a todas las pantallas: es la "pantalla principal" a la que vuelven el portal y el estado público. */
const ACCESOS: { ruta: string; titulo: string; detalle: string; icono: LucideIcon }[] = [
  { ruta: "/mapa", titulo: "Mapa en vivo", detalle: "Antenas, zonas y mapa de calor", icono: Map },
  { ruta: "/linea-tiempo", titulo: "Línea de tiempo", detalle: "Rebobina la red y simula", icono: Film },
  { ruta: "/colectivos", titulo: "Incidentes colectivos", detalle: "Flujo, prioridad y cierre", icono: Siren },
  { ruta: "/incidencias", titulo: "Incidencias", detalle: "Reportes de los usuarios", icono: ListChecks },
  { ruta: "/analitica", titulo: "Analítica", detalle: "Zonas, antenas y tendencias", icono: BarChart3 },
  { ruta: "/nubes", titulo: "Nubes conectadas", detalle: "AWS, Azure e IA", icono: Cloud },
  { ruta: "/portal", titulo: "Estado público", detalle: "Lo que ven los clientes", icono: ChartArea },
  { ruta: "/portal/reportar", titulo: "Portal de usuario", detalle: "Reportar un problema", icono: Smartphone },
];

/** Inicio del centro de control: el resumen de la red en una sola pantalla y la puerta a todas las demás. */
export function Inicio({ antenas, zonas, colectivos, enVivo }: Props) {
  const [buscar, setBuscar] = useState(false);
  const estado = usePolling<EstadoRed>(useCallback(() => apiPortal.estado(), []), 30_000);
  useAlCambiar(["incidencias", "colectivos"], estado.refrescar, 3000);
  const escenario = usePolling<EstadoEscenario>(useCallback(() => apiEscenarios.estado(), []), 5000);

  const activos = colectivos.filter((c) => c.estado !== "CERRADO" && c.estado !== "SERVICIO_RESTABLECIDO");
  const cola = [...activos].sort((a, b) => b.puntajePrioridad - a.puntajePrioridad);
  const cuenta = (e: string) => antenas.filter((a) => a.estado === e).length;
  const operativas = cuenta("NORMAL") + cuenta("SATURADA");
  const enFalla = cuenta("CAIDA") + cuenta("INHABILITADA");
  const enRiesgo = zonas.filter((z) => GRAVEDAD[z.estado] >= GRAVEDAD.CAIDA).reduce((s, z) => s + z.clientesEstimados, 0);
  const trafico = antenas.reduce((s, a) => s + (a.gbPorMinuto ?? 0), 0);
  const ordenadas = [...zonas].sort((a, b) => GRAVEDAD[b.estado] - GRAVEDAD[a.estado] || b.criticidad - a.criticidad);

  // Estado general: lo peor entre lo que dice la red (antenas, incidentes) y lo que reportan los usuarios.
  const nivel = activos.length || enFalla ? "PROBLEMAS" : estado.datos?.nivel ?? "SIN_PROBLEMAS";
  const n = NIVEL_RED[nivel];
  const resumen = activos.length
    ? `${activos.length} incidente${activos.length > 1 ? "s" : ""} colectivo${activos.length > 1 ? "s" : ""} en curso · ${enFalla} antena${enFalla === 1 ? "" : "s"} en falla`
    : enFalla ? `${enFalla} antena${enFalla === 1 ? "" : "s"} en falla, sin incidente colectivo abierto`
    : estado.datos?.mensaje ?? "Todas las zonas operan con normalidad";
  const sim = escenario.datos?.activo ? escenario.datos : null;

  return (
    <ShellNeu titulo="Inicio" enVivo={enVivo} colectivosActivos={activos.length} onBuscar={() => setBuscar(true)}>
      <PaletaComandos abierta={buscar} onAbrir={() => setBuscar(true)} onCerrar={() => setBuscar(false)} zonas={zonas} antenas={antenas}
        onZona={(z) => navegar(`/mapa?zona=${z.zonaId}`)} onAntena={(a) => navegar(`/mapa?antena=${a.antenaId}`)} />

      <div className="scroll-fino -m-1 min-h-0 flex-1 overflow-y-auto p-1">
        <div className="grid grid-cols-[minmax(0,1fr)] gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-5">
            {/* Estado general */}
            <section className="neu flex flex-col gap-5 p-5 sm:flex-row sm:items-center">
              <Anillo proporcion={antenas.length ? operativas / antenas.length : 0} tamano={118} grosor={11}>
                <div className="text-center">
                  <Cifra valor={operativas} className="text-2xl font-bold" />
                  <div className="text-[10px] text-tenue">de {antenas.length} antenas</div>
                </div>
              </Anillo>
              <div className="min-w-0 flex-1">
                <div className="text-xs uppercase tracking-wider text-tenue">Estado de la red</div>
                <div className="mt-1 flex items-center gap-2 text-2xl font-bold" style={{ color: n.color }}>
                  <n.icono className="size-6 shrink-0" /> {n.corto === "Normal" ? "Operando con normalidad" : n.corto}
                </div>
                <p className="mt-1 text-sm text-tenue">{resumen}</p>
                <AnimatePresence>
                  {sim && (
                    <motion.a {...enlace("/linea-tiempo")} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                      className="mt-3 inline-flex items-center gap-2 rounded-full bg-acento/15 px-3 py-1 text-[11px] font-semibold text-acento">
                      <Zap className="latido size-3.5" /> Simulación en curso{sim.narrativa ? ` · ${sim.narrativa}` : ""} — ver en la línea de tiempo
                    </motion.a>
                  )}
                </AnimatePresence>
              </div>
            </section>

            {/* Indicadores */}
            <section className="grid grid-cols-2 gap-5 lg:grid-cols-4">
              <Kpi icono={Siren} color="#a78bfa" etiqueta="Incidentes en curso" valor={activos.length} ruta="/colectivos" />
              <Kpi icono={TowerControl} color={COLOR_NEU.CAIDA} etiqueta="Antenas en falla" valor={enFalla} ruta="/mapa" />
              <Kpi icono={Flame} color="#f472b6" etiqueta="Reportes (24 h)" valor={estado.datos?.totales.ultimas24h ?? 0}
                extra={estado.datos ? `${estado.datos.totales.ultimaHora} en la última hora` : undefined} ruta="/incidencias" />
              <Kpi icono={Users} color={enRiesgo ? COLOR_NEU.CAIDA : COLOR_NEU.NORMAL} etiqueta="Clientes en zonas con falla" valor={enRiesgo}
                extra={`${numero(Math.round(trafico))} GB/min de tráfico`} ruta="/mapa" />
            </section>

            {/* Reportes de 24 h contra lo normal */}
            <section className="neu p-5">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm text-tenue">Reportes de usuarios · últimas 24 h</span>
                <span className="flex items-center gap-3 text-[11px] text-tenue">
                  <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-acento" /> Reportes</span>
                  <span className="flex items-center gap-1.5"><span className="h-0 w-4 border-t border-dashed border-tenue" /> Lo normal</span>
                </span>
              </div>
              {estado.datos ? <GraficoReportes serie={estado.datos.serie} />
                : <div className="grid h-56 place-items-center text-xs text-tenue">{estado.error ?? "Cargando…"}</div>}
            </section>

            {/* Accesos */}
            <section>
              <div className="mb-3 px-1 text-sm text-tenue">Ir a</div>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {ACCESOS.map((a) => (
                  <a key={a.ruta} {...enlace(a.ruta)}
                    className="boton-neu group flex flex-col items-start gap-3 p-4 text-left">
                    <span className="grid size-10 place-items-center rounded-2xl bg-acento/12 text-acento transition-colors group-hover:bg-acento/20">
                      <a.icono className="size-5" />
                    </span>
                    <span>
                      <span className="block text-sm font-semibold text-texto">{a.titulo}</span>
                      <span className="block text-[11px] text-tenue">{a.detalle}</span>
                    </span>
                  </a>
                ))}
              </div>
            </section>
          </div>

          {/* Columna derecha */}
          <div className="flex min-w-0 flex-col gap-5">
            <section className="neu p-3">
              <a {...enlace("/colectivos")} className="flex items-center gap-2 px-2 pb-2 pt-1 text-sm text-tenue hover:text-texto">
                <ListOrdered className="size-4 text-acento" /> Cola de atención <ChevronRight className="ml-auto size-4" />
              </a>
              {cola.length ? (
                <ol className="space-y-1">
                  <AnimatePresence initial={false}>
                    {cola.slice(0, 5).map((c, i) => (
                      <motion.li key={c.incidenteColectivoId} layout="position" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                        transition={{ duration: 0.15, layout: { type: "spring", stiffness: 500, damping: 40 } }}>
                        <button onClick={() => navegar(`/colectivos?id=${c.incidenteColectivoId}`)}
                          className="flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-panel-2">
                          <span className={cn("grid size-7 shrink-0 place-items-center rounded-full text-xs font-bold", i === 0 ? "degradado text-white" : "neu-hundido text-tenue")}>{i + 1}</span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">{c.zona.nombre}</span>
                            <span className="block truncate text-[11px]" style={{ color: ESTADO_COLECTIVO[c.estado].color }}>
                              {ESTADO_COLECTIVO[c.estado].etiqueta} · {c.afectados} afectados · {haceCuanto(c.detectadoEn)}
                            </span>
                          </span>
                          <span className="text-[11px] font-semibold" style={{ color: PRIORIDAD[c.prioridad].color }}>{PRIORIDAD[c.prioridad].etiqueta}</span>
                        </button>
                      </motion.li>
                    ))}
                  </AnimatePresence>
                </ol>
              ) : (
                <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
                  <Radio className="size-7 text-normal" />
                  <span className="text-sm font-medium">Sin incidentes en curso</span>
                  <span className="text-[11px] text-tenue">Cuando 10 usuarios de una zona reporten o una antena caiga, aparecerá aquí.</span>
                </div>
              )}
            </section>

            <section className="neu p-3">
              <a {...enlace("/mapa")} className="flex items-center justify-between px-2 pb-2 pt-1 text-sm text-tenue hover:text-texto">
                Zonas <span className="flex items-center gap-1 text-[11px]">{zonas.length} <ChevronRight className="size-4" /></span>
              </a>
              <ul className="space-y-0.5">
                {ordenadas.map((z) => {
                  const Icono = TIPO_ZONA[z.tipo].icono;
                  const color = COLOR_NEU[z.estado];
                  const reportes = estado.datos?.zonas.find((x) => x.zonaId === z.zonaId)?.total24h ?? 0;
                  return (
                    <motion.li key={z.zonaId} layout transition={{ type: "spring", stiffness: 500, damping: 40 }}>
                      <button onClick={() => navegar(`/mapa?zona=${z.zonaId}`)}
                        className="flex w-full items-center gap-3 rounded-xl px-2 py-1.5 text-left transition-colors hover:bg-panel-2">
                        <span className="grid size-8 shrink-0 place-items-center rounded-xl" style={{ background: `${color}1f`, color }}><Icono className="size-4" /></span>
                        <span className="min-w-0 flex-1 truncate text-sm">{z.nombre}</span>
                        {reportes > 0 && <span className="cifra text-[11px] text-tenue">{reportes} rep.</span>}
                        <span className="w-20 text-right text-[11px] font-semibold" style={{ color }}>{ESTADO[z.estado].etiqueta}</span>
                      </button>
                    </motion.li>
                  );
                })}
              </ul>
            </section>
          </div>
        </div>
      </div>
    </ShellNeu>
  );
}

function Kpi({ icono: Icono, color, etiqueta, valor, extra, ruta }: { icono: LucideIcon; color: string; etiqueta: string; valor: number; extra?: string; ruta: string }) {
  return (
    <a {...enlace(ruta)} className="neu group flex flex-col gap-3 p-4 transition-transform hover:-translate-y-0.5">
      <span className="flex items-center justify-between">
        <span className="grid size-9 place-items-center rounded-xl" style={{ background: `${color}1f`, color }}><Icono className="size-4" /></span>
        <ChevronRight className="size-4 text-tenue opacity-0 transition-opacity group-hover:opacity-100" />
      </span>
      <span>
        <Cifra valor={valor} className="block text-2xl font-bold" />
        <span className="block text-xs text-tenue">{etiqueta}</span>
        {extra && <span className="mt-0.5 block text-[10px] text-tenue/80">{extra}</span>}
      </span>
    </a>
  );
}
