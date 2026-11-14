import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, Flame, RotateCcw, Siren, Users, Zap } from "lucide-react";
import { api, apiIncidencias, type Antena, type Colectivo, type EstadoSimulador, type Incidencia, type Zona } from "../lib/api";
import { ESTADO, ESTADO_COLECTIVO, GRAVEDAD, ORDEN_ESTADOS, PRIORIDAD, TIPO_ZONA } from "../lib/estados";
import { usePolling } from "../hooks/usePolling";
import { navegar } from "../lib/router";
import { cn, haceCuanto, numero } from "../lib/utils";
import { MapaRed } from "../components/MapaRed";
import { ShellNeu } from "../components/neu/ShellNeu";
import { PaletaComandos } from "../components/neu/PaletaComandos";
import { DetalleAntenaNeu } from "../components/neu/DetalleAntenaNeu";
import { Anillo, Cifra, Interruptor, PasosColectivo } from "../components/neu/Piezas";
import { COLOR_NEU, PALETA_MAPA_NEU } from "../components/neu/paleta";

interface Props {
  antenas: Antena[];
  zonas: Zona[];
  colectivos: Colectivo[];
  enVivo: boolean;
  refrescarRed: () => void;
}

/** Centro de control rediseñado (estilo neumórfico, issue #28). */
export function MapaNeu({ antenas, zonas, colectivos, enVivo, refrescarRed }: Props) {
  const sim = usePolling<EstadoSimulador>(api.simulador, 10_000);
  const reportes = usePolling<Incidencia[]>(useCallback(() => apiIncidencias.listar({ horas: 24 }).then((r) => r.incidencias), []), 10_000);
  const [verCalor, setVerCalor] = useState(true);
  // ?antena=ANT-013 o ?zona=ZONA-05 (desde la paleta Ctrl+K de otras pantallas)
  const params = new URLSearchParams(window.location.search);
  const [seleccion, setSeleccion] = useState<string | null>(params.get("antena"));
  const [zonaFoco, setZonaFoco] = useState<Zona | null>(null);
  const zonaInicial = params.get("zona") ?? antenas.find((a) => a.antenaId === params.get("antena"))?.zonaId;
  useEffect(() => {
    if (zonaFoco || !zonaInicial) return;
    const z = zonas.find((x) => x.zonaId === zonaInicial);
    if (z) setZonaFoco({ ...z });
  }, [zonas, zonaInicial, zonaFoco]);
  const [buscar, setBuscar] = useState(false);
  const [ocupado, setOcupado] = useState(false);

  const antenaSel = antenas.find((a) => a.antenaId === seleccion) ?? null;
  const activos = colectivos.filter((c) => c.estado !== "CERRADO");
  const principal = activos[0];
  const cuenta = (e: string) => antenas.filter((a) => a.estado === e).length;
  const operativas = cuenta("NORMAL") + cuenta("SATURADA");
  const trafico = antenas.reduce((s, a) => s + (a.gbPorMinuto ?? 0), 0);
  const enRiesgo = zonas.filter((z) => GRAVEDAD[z.estado] >= GRAVEDAD.CAIDA).reduce((s, z) => s + z.clientesEstimados, 0);
  const ordenadas = [...zonas].sort((a, b) => GRAVEDAD[b.estado] - GRAVEDAD[a.estado] || b.criticidad - a.criticidad);

  const cambiarSimulador = async (cambios: Parameters<typeof api.actualizarSimulador>[0]) => {
    setOcupado(true);
    try { await api.actualizarSimulador(cambios); await sim.refrescar(); setTimeout(refrescarRed, 1500); }
    finally { setOcupado(false); }
  };
  const fallas = Object.keys(sim.datos?.fallas ?? {}).length;

  return (
    <ShellNeu titulo="Centro de control" enVivo={enVivo} colectivosActivos={activos.length} onBuscar={() => setBuscar(true)}
      acciones={
        <div className="neu-chico flex h-11 items-center gap-3 pl-4 pr-2">
          <Zap className="size-4 text-acento" />
          <div className="text-xs leading-tight">
            <div className="font-semibold">Simulador</div>
            <div className="text-[10px] text-tenue">{sim.datos?.activo ? `${sim.datos.muestrasPorMinuto} lecturas/min` : "apagado · $0"}{fallas ? ` · ${fallas} falla${fallas > 1 ? "s" : ""}` : ""}</div>
          </div>
          {fallas > 0 && (
            <button onClick={() => cambiarSimulador({ limpiarFallas: true })} title="Quitar fallas forzadas" aria-label="Quitar fallas forzadas"
              className="boton-neu grid size-8 place-items-center text-tenue"><RotateCcw className="size-3.5" /></button>
          )}
          <Interruptor etiqueta="Encender o apagar el simulador" activo={!!sim.datos?.activo} deshabilitado={!sim.datos || ocupado}
            onClick={() => cambiarSimulador({ activo: !sim.datos?.activo })} />
        </div>
      }>
      <PaletaComandos abierta={buscar} onAbrir={() => setBuscar(true)} onCerrar={() => setBuscar(false)} zonas={zonas} antenas={antenas}
        onZona={(z) => { setZonaFoco({ ...z }); setSeleccion(null); }}
        onAntena={(a) => { setSeleccion(a.antenaId); const z = zonas.find((x) => x.zonaId === a.zonaId); if (z) setZonaFoco({ ...z }); }} />

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
        {/* Columna de indicadores */}
        <aside className="scroll-fino order-2 flex min-h-0 flex-col gap-5 overflow-y-auto p-1 lg:order-1">
          <section className="neu flex flex-col items-center gap-4 p-5">
            <div className="self-start text-sm text-tenue">Antenas operativas</div>
            <Anillo proporcion={antenas.length ? operativas / antenas.length : 0}>
              <div className="text-center">
                <Cifra valor={operativas} className="text-3xl font-bold" />
                <div className="text-xs text-tenue">de {antenas.length}</div>
              </div>
            </Anillo>
            <div className="grid w-full grid-cols-2 gap-x-4 gap-y-2">
              {ORDEN_ESTADOS.map((e) => (
                <div key={e} className="flex items-center gap-2 text-xs">
                  <span className="size-2.5 rounded-full" style={{ background: COLOR_NEU[e] }} />
                  <span className="text-tenue">{ESTADO[e].etiqueta}</span>
                  <Cifra valor={cuenta(e)} className="ml-auto font-semibold" />
                </div>
              ))}
            </div>
          </section>

          <section className="neu p-5">
            <div className="text-sm text-tenue">Tráfico total</div>
            <div className="mt-1 flex items-baseline gap-1.5">
              <Cifra valor={Math.round(trafico)} className="text-3xl font-bold" />
              <span className="text-xs text-tenue">GB/min</span>
            </div>
            <div className="mt-3 space-y-2 text-xs">
              <div className="flex items-center gap-2"><Users className="size-3.5" style={{ color: enRiesgo ? COLOR_NEU.CAIDA : undefined }} />
                <span className="text-tenue">Clientes en zonas con falla</span><Cifra valor={enRiesgo} className="ml-auto font-semibold" /></div>
              <div className="flex items-center gap-2"><Flame className="size-3.5 text-[#e05ab0]" />
                <span className="text-tenue">Reportes de usuarios (24 h)</span><Cifra valor={reportes.datos?.length ?? 0} className="ml-auto font-semibold" /></div>
            </div>
          </section>

          <section className="neu p-3">
            <div className="flex items-center justify-between px-2 pb-2 pt-1">
              <span className="text-sm text-tenue">Zonas por gravedad</span>
              <span className="text-[11px] text-tenue">{zonas.length}</span>
            </div>
            <ul className="space-y-1">
              {ordenadas.map((z) => {
                const Icono = TIPO_ZONA[z.tipo].icono;
                const color = COLOR_NEU[z.estado];
                return (
                  <motion.li key={z.zonaId} layout transition={{ type: "spring", stiffness: 500, damping: 40 }}>
                    <button onClick={() => { setZonaFoco({ ...z }); setSeleccion(null); }}
                      className="flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-panel-2">
                      <span className="grid size-9 shrink-0 place-items-center rounded-xl" style={{ background: `${color}1f`, color }}>
                        <Icono className="size-4" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{z.nombre}</span>
                        <span className="block text-[11px] text-tenue">{TIPO_ZONA[z.tipo].etiqueta} · {numero(z.clientesEstimados)} clientes</span>
                      </span>
                      <span className="text-[11px] font-semibold" style={{ color }}>{ESTADO[z.estado].etiqueta}</span>
                    </button>
                  </motion.li>
                );
              })}
            </ul>
          </section>
        </aside>

        {/* Columna del mapa */}
        <section className="order-1 flex min-h-0 flex-col gap-5 lg:order-2">
          <AnimatePresence>
            {principal && (
              <motion.button key={principal.incidenteColectivoId}
                initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
                onClick={() => navegar(`/colectivos?id=${principal.incidenteColectivoId}`)}
                className="neu flex items-center gap-4 p-3 pr-4 text-left">
                <span className="degradado grid size-11 shrink-0 place-items-center rounded-2xl text-white"><Siren className="latido size-5" /></span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold">Incidente colectivo · {principal.zona.nombre}</span>
                  <span className="block truncate text-xs text-tenue">
                    {ESTADO_COLECTIVO[principal.estado].etiqueta} · {principal.afectados} usuarios · {principal.antenasEnFalla.length} antena(s) en falla · {haceCuanto(principal.detectadoEn)}
                    {activos.length > 1 && ` · +${activos.length - 1} más`}
                  </span>
                </span>
                <span className="rounded-full px-3 py-1 text-[10px] font-bold text-white"
                  style={{ background: PRIORIDAD[principal.prioridad].color }}>{PRIORIDAD[principal.prioridad].etiqueta}</span>
                <ChevronRight className="size-4 text-tenue" />
              </motion.button>
            )}
          </AnimatePresence>

          <div className="neu-hundido relative min-h-[55vh] flex-1 overflow-hidden p-1.5">
            <div className="relative h-full min-h-[55vh] overflow-hidden rounded-[13px]">
              <MapaRed antenas={antenas} zonas={zonas} colectivos={colectivos} reportes={verCalor ? reportes.datos ?? [] : []}
                seleccion={seleccion} onSeleccionar={setSeleccion} enfocarZona={zonaFoco} paleta={PALETA_MAPA_NEU} />
              <DetalleAntenaNeu antena={antenaSel} zona={zonas.find((z) => z.zonaId === antenaSel?.zonaId)}
                forzada={antenaSel ? sim.datos?.fallas[antenaSel.antenaId] : undefined}
                onCerrar={() => setSeleccion(null)} onForzar={(id, v) => cambiarSimulador({ fallas: { [id]: v } })} />
              <div className="neu-chico absolute bottom-4 left-4 right-16 z-10 flex flex-wrap lg:right-auto items-center gap-x-4 gap-y-1 px-4 py-2 text-[11px]">
                {ORDEN_ESTADOS.map((e) => (
                  <span key={e} className="flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ background: COLOR_NEU[e] }} />{ESTADO[e].etiqueta}</span>
                ))}
                <button onClick={() => setVerCalor(!verCalor)} data-activo={verCalor}
                  className={cn("boton-neu flex items-center gap-1.5 px-2.5 py-1", verCalor ? "text-[#e05ab0]" : "text-tenue")}>
                  <Flame className="size-3" /> Reportes
                </button>
              </div>
            </div>
          </div>

          {principal && (
            <div className="neu px-5 py-4">
              <PasosColectivo colectivo={principal} />
            </div>
          )}
        </section>
      </div>
    </ShellNeu>
  );
}
