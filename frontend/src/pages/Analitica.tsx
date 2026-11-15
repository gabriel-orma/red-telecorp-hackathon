import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { Clock, Loader2, Radar, RadioTower, ShieldAlert, Siren, Timer, Users } from "lucide-react";
import { apiAnalitica, type Analitica as Datos } from "../lib/api";
import { PRIORIDAD, TIPO_PROBLEMA, TIPO_ZONA } from "../lib/estados";
import { usePolling } from "../hooks/usePolling";
import { navegar } from "../lib/router";
import { cn, haceCuanto } from "../lib/utils";
import { Cifra } from "../components/neu/Piezas";
import { COLOR_NEU } from "../components/neu/paleta";

const RANGOS = [1, 7, 30];
const EJE = { fill: "#8b8b97", fontSize: 11 };
const TOOLTIP = { contentStyle: { background: "#1c1c21", border: "none", borderRadius: 14, boxShadow: "6px 6px 16px #0a0a0c", fontSize: 12 },
                  labelStyle: { color: "#ececf1", fontWeight: 600 }, cursor: { fill: "#ffffff08" } };
const minutos = (m: number | null) => m === null ? "—" : m >= 60 ? `${(m / 60).toFixed(1)} h` : `${Math.round(m)} min`;

/** Analítica operativa (E6): zonas, antenas, tipos, duración, detección anticipada y recurrencia. */
export function Analitica() {
  const [dias, setDias] = useState(7);
  // Lo operativo y lo simulado NO se mezclan nunca: el panel muestra uno u otro (por defecto, lo operativo).
  const [simulados, setSimulados] = useState(false);
  const datos = usePolling<Datos>(useCallback(() => apiAnalitica.obtener(dias, simulados), [dias, simulados]), 60_000);
  const [ejecutando, setEjecutando] = useState(false);
  const d = datos.datos?.dias === dias && (datos.datos.datos === "SIMULADOS") === simulados ? datos.datos : null;

  const recurrencia = async () => {
    setEjecutando(true);
    try {
      await apiAnalitica.recurrencia(simulados);
      toast.custom(() => <div className="tema-neu neu-chico px-4 py-3 text-sm">Análisis de recurrencia en curso (Step Functions)…</div>, { duration: 4000 });
      setTimeout(datos.refrescar, 8000);
    } finally { setEjecutando(false); }
  };

  return (
    <main className="scroll-fino min-h-0 flex-1 space-y-5 overflow-y-auto p-1">
      <div className="flex flex-wrap items-center gap-3">
        <div className="neu-hundido flex p-1">
          {RANGOS.map((r) => (
            <button key={r} onClick={() => setDias(r)} aria-pressed={dias === r}
              className={cn("rounded-xl px-4 py-1.5 text-xs font-medium transition-colors", dias === r ? "degradado text-white" : "text-tenue hover:text-texto")}>
              {r === 1 ? "24 h" : `${r} días`}
            </button>
          ))}
        </div>
        <div className="neu-hundido flex p-1" role="group" aria-label="Universo de datos">
          {([[false, "Operativos"], [true, "Simulación"]] as const).map(([valor, texto]) => (
            <button key={texto} onClick={() => setSimulados(valor)} aria-pressed={simulados === valor}
              className={cn("rounded-xl px-4 py-1.5 text-xs font-medium transition-colors", simulados === valor ? "degradado text-white" : "text-tenue hover:text-texto")}>
              {texto}
            </button>
          ))}
        </div>
        {datos.datos && <span className="text-xs text-tenue">Actualizado {haceCuanto(datos.datos.generadoEn)}</span>}
        {datos.error && <span role="alert" className="text-xs text-caida">No se pudo actualizar la analítica; se muestra el último dato recibido.</span>}
      </div>
      {simulados && (
        <p role="status" className="rounded-xl bg-acento/10 px-4 py-2 text-xs text-tenue ring-1 ring-acento/30">
          Mostrando <b className="text-texto">solo datos de simulación</b> (escenarios de demo y fallas forzadas). Los datos operativos no se mezclan con estos.
        </p>
      )}

      {!d ? <div className="grid h-64 place-items-center"><Loader2 className="size-6 animate-spin text-tenue" /></div> : (<>
        {/* KPIs */}
        <section className="grid grid-cols-2 gap-5 lg:grid-cols-4">
          <Kpi icono={Siren} etiqueta="Incidentes colectivos" valor={d.kpis.incidentes} pie={`${d.kpis.abiertos} abiertos${d.kpis.requierenAtencion ? ` · ${d.kpis.requierenAtencion} requieren atención` : ""}`} />
          <Kpi icono={Users} etiqueta="Usuarios afectados" valor={d.kpis.afectadosTotales} pie={`${d.kpis.reportes} reportes en total`} />
          <Kpi icono={Timer} etiqueta="Duración promedio" texto={minutos(d.kpis.duracionPromedioMin)} pie="de los incidentes cerrados" />
          <Kpi icono={Radar} etiqueta="Detectados primero por la red" valor={d.kpis.detectadosPrimeroPorLaRed}
            pie={d.kpis.deteccionAnticipadaPromedioMin !== null ? `mediana: ${minutos(Math.abs(d.kpis.deteccionAnticipadaPromedioMin))} ${d.kpis.deteccionAnticipadaPromedioMin >= 0 ? "antes" : "después"} que los usuarios` : "antes que cualquier reporte"}
            destacado />
        </section>

        <div className="grid gap-5 xl:grid-cols-2">
          {/* Zonas */}
          <Tarjeta titulo="Zonas con más incidentes" subtitulo="Rosa: incidentes colectivos · lila: reportes de usuarios (escalas independientes)">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={d.zonas.slice(0, 8)} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid horizontal={false} stroke="#2a2a31" />
                {/* Escalas separadas: los incidentes son pocos y los reportes cientos */}
                <XAxis xAxisId="rep" type="number" tick={EJE} axisLine={false} tickLine={false} allowDecimals={false} />
                <XAxis xAxisId="inc" type="number" hide allowDecimals={false} domain={[0, (max: number) => Math.max(1, max)]} />
                <YAxis type="category" dataKey="nombre" width={130} tick={EJE} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP} />
                <Bar xAxisId="rep" dataKey="reportes" name="Reportes" fill="#a78bfa" fillOpacity={0.35} radius={[0, 6, 6, 0]} barSize={10} />
                <Bar xAxisId="inc" dataKey="incidentes" name="Incidentes" fill="#e05ab0" radius={[0, 6, 6, 0]} barSize={10} />
              </BarChart>
            </ResponsiveContainer>
          </Tarjeta>

          {/* Duración de incidentes */}
          <Tarjeta titulo="Duración y alcance de los incidentes" subtitulo="Cada barra es un incidente, coloreada por prioridad">
            {d.incidentes.length === 0 ? <Vacio texto="Sin incidentes en el periodo." /> : (
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={d.incidentes.map((i) => ({ ...i, etiqueta: `${i.nombre} · ${new Date(i.detectadoEn).toLocaleTimeString("es-PE", { hour: "2-digit", minute: "2-digit" })}` }))}
                  margin={{ left: -10, right: 8 }}>
                  <CartesianGrid vertical={false} stroke="#2a2a31" />
                  <XAxis dataKey="etiqueta" tick={false} axisLine={{ stroke: "#2a2a31" }} />
                  <YAxis tick={EJE} axisLine={false} tickLine={false} unit=" m" scale="sqrt" domain={[0, "auto"]} />
                  <Tooltip {...TOOLTIP} formatter={(v, n) => [n === "duracionMin" ? minutos(Number(v)) : String(v), n === "duracionMin" ? "Duración" : "Afectados"] as [string, string]} />
                  <Bar dataKey="duracionMin" radius={[6, 6, 0, 0]} onClick={(x) => navegar(`/colectivos?id=${(x as unknown as { incidenteColectivoId: string }).incidenteColectivoId}`)} cursor="pointer">
                    {d.incidentes.map((i) => <Cell key={i.incidenteColectivoId} fill={PRIORIDAD[i.prioridad]?.color ?? "#a78bfa"} fillOpacity={i.abierto ? 1 : 0.7} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </Tarjeta>

          {/* Tipos */}
          <Tarjeta titulo="Problemas más reportados">
            {d.tipos.length === 0 ? <Vacio texto="Sin reportes en el periodo." /> : (
              <ul className="space-y-3">
                {d.tipos.map((t) => {
                  const I = TIPO_PROBLEMA[t.tipo]?.icono ?? TIPO_PROBLEMA.OTRO.icono;
                  return (
                    <li key={t.tipo}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="flex items-center gap-2"><I className="size-4 text-acento" />{TIPO_PROBLEMA[t.tipo]?.etiqueta ?? t.tipo}</span>
                        <span className="text-xs text-tenue"><Cifra valor={t.total} /> · {t.pct}%</span>
                      </div>
                      <div className="neu-hundido h-2.5 overflow-hidden rounded-full">
                        <motion.div className="degradado h-full rounded-full" initial={{ width: 0 }} animate={{ width: `${t.pct}%` }} transition={{ duration: 0.6, ease: [0.23, 1, 0.32, 1] }} />
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Tarjeta>

          {/* Antenas + recurrencia */}
          <Tarjeta titulo="Antenas con más fallas" subtitulo={`Estructural: ${d.recurrencia.umbralFallas}+ fallas en ${d.recurrencia.ventanaDias} días · último análisis ${d.recurrencia.ultimaEjecucion ? haceCuanto(d.recurrencia.ultimaEjecucion) : "nunca"}`}
            accion={
              <button onClick={recurrencia} disabled={ejecutando} className="boton-neu flex items-center gap-1.5 px-3 py-2 text-xs font-semibold text-acento disabled:opacity-50">
                {ejecutando ? <Loader2 className="size-3.5 animate-spin" /> : <ShieldAlert className="size-3.5" />} Analizar ahora
              </button>
            }>
            {d.antenas.length === 0 ? <Vacio texto="Ninguna antena falló en el periodo." /> : (
              <ul className="space-y-1">
                {d.antenas.slice(0, 8).map((a) => {
                  const max = d.antenas[0].fallas || 1;
                  return (
                    <li key={a.antenaId}>
                      <button onClick={() => navegar(`/mapa?antena=${a.antenaId}`)} className="flex w-full items-center gap-3 rounded-xl px-2 py-1.5 text-left hover:bg-panel-2">
                        <RadioTower className="size-4 shrink-0" style={{ color: a.estructural ? COLOR_NEU.CAIDA : "#8b8b97" }} />
                        <span className="w-24 shrink-0">
                          <span className="cifra block text-sm font-semibold">{a.antenaId}</span>
                          <span className="block truncate text-[11px] text-tenue">{a.zona}</span>
                        </span>
                        <span className="neu-hundido h-2 flex-1 overflow-hidden rounded-full">
                          <span className="block h-full rounded-full" style={{ width: `${(100 * a.fallas) / max}%`, background: a.estructural ? COLOR_NEU.CAIDA : "#a78bfa" }} />
                        </span>
                        <span className="w-8 text-right text-sm font-semibold"><Cifra valor={a.fallas} /></span>
                        {a.estructural && <span className="rounded-full bg-caida/15 px-2 py-0.5 text-[10px] font-semibold text-caida">Estructural</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </Tarjeta>
        </div>

        {/* Ranking de zonas */}
        <Tarjeta titulo="Detalle por zona">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {d.zonas.map((z) => {
              const I = TIPO_ZONA[z.tipo].icono;
              return (
                <div key={z.zonaId} className="neu-hundido flex items-center gap-3 px-3 py-2.5">
                  <I className="size-4 shrink-0 text-tenue" />
                  <span className="min-w-0 flex-1 truncate text-sm">{z.nombre}</span>
                  <span className="text-[11px] text-tenue"><b className="text-texto">{z.incidentes}</b> inc · {z.reportes} rep</span>
                </div>
              );
            })}
          </div>
        </Tarjeta>
      </>)}

    </main>
  );
}

function Kpi({ icono: Icono, etiqueta, valor, texto, pie, destacado }: { icono: typeof Clock; etiqueta: string; valor?: number; texto?: string; pie: string; destacado?: boolean }) {
  return (
    <div className="neu p-5">
      <div className="flex items-center gap-2 text-sm text-tenue">
        <span className={cn("grid size-8 place-items-center rounded-xl", destacado ? "degradado text-white" : "neu-hundido text-acento")}><Icono className="size-4" /></span>
        {etiqueta}
      </div>
      <div className="mt-3 text-3xl font-bold">{valor !== undefined ? <Cifra valor={valor} /> : texto}</div>
      <div className="mt-1 text-xs text-tenue">{pie}</div>
    </div>
  );
}

function Tarjeta({ titulo, subtitulo, accion, children }: { titulo: string; subtitulo?: string; accion?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="neu p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div><h2 className="text-sm font-semibold">{titulo}</h2>{subtitulo && <p className="text-xs text-tenue">{subtitulo}</p>}</div>
        {accion}
      </div>
      {children}
    </section>
  );
}

function Vacio({ texto }: { texto: string }) {
  return <div className="grid h-40 place-items-center text-sm text-tenue">{texto}</div>;
}
