import { useCallback, useState } from "react";
import { motion } from "framer-motion";
import { CheckCircle2, ExternalLink, Loader2, Megaphone, RadioTower, ShieldAlert, Users } from "lucide-react";
import { apiColectivos, type Colectivo, type DetalleColectivo } from "../lib/api";
import { ESTADO, ESTADO_COLECTIVO, PRIORIDAD, TIPO_PROBLEMA, TIPO_ZONA } from "../lib/estados";
import { usePolling } from "../hooks/usePolling";
import { navegar } from "../lib/router";
import { cn, haceCuanto, numero } from "../lib/utils";
import { FlujoColectivo, FlujoMini } from "../components/FlujoColectivo";
import { ChipEstado, Historial } from "../components/LineaTiempo";

const ORIGEN = { REPORTES_USUARIOS: "Reportes de usuarios", METRICAS_ANTENA: "Detección proactiva (antena)", AMBOS: "Usuarios + antenas" };

export function Colectivos({ abiertos }: { abiertos: Colectivo[] | null }) {
  const [verTodos, setVerTodos] = useState(false);
  const todos = usePolling(useCallback(() => apiColectivos.listar(true).then((r) => r.colectivos), []), 5000);
  const lista = verTodos ? todos.datos : abiertos;
  const seleccion = new URLSearchParams(window.location.search).get("id") ?? lista?.[0]?.incidenteColectivoId ?? null;

  return (
    <main className="flex min-h-0 flex-1 flex-col gap-5 md:flex-row">
      <section className="panel flex w-full shrink-0 flex-col overflow-hidden md:w-[360px]">
        <div className="flex items-center justify-between border-b border-borde p-3">
          <h1 className="text-sm font-semibold">Incidentes colectivos</h1>
          <div className="flex rounded-lg bg-fondo p-0.5 text-[11px] ring-1 ring-borde">
            {[false, true].map((t) => (
              <button key={String(t)} onClick={() => setVerTodos(t)}
                className={cn("rounded-md px-2 py-1", verTodos === t ? "bg-panel-2 text-texto" : "text-tenue")}>
                {t ? "Últimos 7 días" : "Activos"}
              </button>
            ))}
          </div>
        </div>
        <ul className="scroll-fino min-h-0 flex-1 space-y-2 overflow-y-auto p-2">
          {!lista && <Loader2 className="mx-auto mt-8 size-5 animate-spin text-tenue" />}
          {lista && !lista.length && (
            <li className="p-6 text-center text-sm text-tenue">
              <CheckCircle2 className="mx-auto mb-2 size-8 text-normal/70" />
              No hay incidentes colectivos {verTodos ? "en los últimos 7 días" : "activos"}.
              <div className="mt-2 text-[11px]">Se crean solos con ≥10 usuarios distintos en una zona (&lt;24 h) o cuando cae una antena.</div>
            </li>
          )}
          {lista?.map((c) => (
            <li key={c.incidenteColectivoId}>
              <button onClick={() => navegar(`/colectivos?id=${c.incidenteColectivoId}`)}
                className={cn("w-full rounded-xl border p-3 text-left transition hover:bg-panel-2/70",
                  c.incidenteColectivoId === seleccion ? "border-acento/60 bg-panel-2" : "border-borde")}>
                <div className="flex items-center justify-between gap-2">
                  <span className="truncate text-sm font-semibold">{c.zona.nombre}</span>
                  <ChipPrioridad c={c} />
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-[11px] text-tenue">
                  <span style={{ color: ESTADO_COLECTIVO[c.estado].color }}>{ESTADO_COLECTIVO[c.estado].etiqueta}</span>
                  · <Users className="size-3" />{c.afectados} · {haceCuanto(c.detectadoEn)}
                </div>
                <div className="mt-2"><FlujoMini colectivo={c} /></div>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {seleccion ? <Detalle key={seleccion} id={seleccion} /> : <div className="panel hidden flex-1 md:block" />}
    </main>
  );
}

function ChipPrioridad({ c }: { c: Colectivo }) {
  const p = PRIORIDAD[c.prioridad];
  return (
    <span className="cifra shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold"
      style={{ background: `${p.color}22`, color: p.color }}>
      {p.etiqueta} · {c.puntajePrioridad}
    </span>
  );
}

function Detalle({ id }: { id: string }) {
  const det = usePolling<DetalleColectivo>(useCallback(() => apiColectivos.obtener(id), [id]), 3000);
  const [enviando, setEnviando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const d = det.datos;
  if (!d) return <section className="panel grid flex-1 place-items-center"><Loader2 className="size-5 animate-spin text-tenue" /></section>;
  const c = d.colectivo;
  const abierto = c.estado === "EN_EVALUACION" || c.estado === "INCIDENCIA_CONFIRMADA";
  const consola = c.ejecucionArn
    ? `https://us-east-1.console.aws.amazon.com/states/home?region=us-east-1#/v2/executions/details/${c.ejecucionArn}`
    : null;

  const restablecer = async () => {
    setEnviando(true);
    try { const r = await apiColectivos.restablecer(id); setAviso(r.mensaje); await det.refrescar(); }
    catch (e) { setAviso(e instanceof Error ? e.message : String(e)); }
    finally { setEnviando(false); }
  };

  return (
    <motion.section initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
      className="scroll-fino grid min-h-0 flex-1 gap-3 overflow-y-auto lg:grid-cols-[1fr_320px]">
      <div className="space-y-3">
        {/* Cabecera */}
        <div className="panel p-4" style={{ background: `linear-gradient(135deg, ${ESTADO_COLECTIVO[c.estado].color}1f, transparent 55%)` }}>
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="cifra text-[11px] text-tenue">{c.incidenteColectivoId}</div>
              <h2 className="text-xl font-semibold">{c.zona.nombre}</h2>
              <div className="text-xs text-tenue">{TIPO_ZONA[c.zona.tipo]?.etiqueta} · {numero(c.zona.clientesEstimados)} clientes · {ORIGEN[c.origen]}</div>
            </div>
            <ChipPrioridad c={c} />
          </div>
          <div className="mt-3 text-lg font-semibold" style={{ color: ESTADO_COLECTIVO[c.estado].color }}>{ESTADO_COLECTIVO[c.estado].etiqueta}</div>
          <div className="text-xs text-tenue">{c.origenDetalle} · detectado {haceCuanto(c.detectadoEn)}
            {c.duracionMinutos !== undefined && ` · duró ${c.duracionMinutos} min`}</div>

          <div className="mt-4 grid grid-cols-3 gap-2 text-center">
            <Kpi icono={Users} valor={c.afectados} etiqueta="usuarios afectados" />
            <Kpi icono={RadioTower} valor={c.antenasEnFalla.length} etiqueta="antenas en falla" color={c.antenasEnFalla.length ? ESTADO.CAIDA.color : undefined} />
            <Kpi icono={Megaphone} valor={c.notificacionesEnviadas} etiqueta="avisos enviados" />
          </div>

          {c.resumenIA && (
            <div className="mt-3 rounded-xl bg-fondo/60 p-3 text-sm">
              <div className="mb-1 text-[10px] text-tenue">Resumen para el operador</div>
              {c.resumenIA}
            </div>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {abierto && (
              <button onClick={restablecer} disabled={enviando || c.restablecimientoSolicitado}
                className="flex items-center gap-1.5 rounded-lg bg-normal/15 px-3 py-2 text-xs font-medium text-normal ring-1 ring-normal/40 hover:bg-normal/25 disabled:opacity-50">
                {enviando ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
                {c.restablecimientoSolicitado ? "Restablecimiento solicitado…" : "Marcar servicio restablecido"}
              </button>
            )}
            {consola && (
              <a href={consola} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-tenue hover:text-acento">
                Ver ejecución en Step Functions <ExternalLink className="size-3" />
              </a>
            )}
            {aviso && <span className="text-[11px] text-tenue">{aviso}</span>}
          </div>
        </div>

        {/* Antenas e incidencias */}
        <div className="grid gap-3 md:grid-cols-2">
          <div className="panel p-4">
            <div className="mb-2 text-[11px] text-tenue">Antenas en falla</div>
            {c.antenasEnFalla.length ? c.antenasEnFalla.map((a) => (
              <div key={a.antenaId} className="flex items-center justify-between py-1 text-sm">
                <span className="cifra">{a.antenaId}</span>
                <span className="text-xs" style={{ color: ESTADO[a.estado as keyof typeof ESTADO]?.color }}>{ESTADO[a.estado as keyof typeof ESTADO]?.etiqueta ?? a.estado}</span>
              </div>
            )) : <div className="flex items-center gap-2 text-xs text-tenue"><ShieldAlert className="size-4" />Ninguna: falla sin causa en la red (revisar en sitio).</div>}
          </div>
          <div className="panel p-4">
            <div className="mb-2 text-[11px] text-tenue">Incidencias agrupadas · {d.incidencias.length}</div>
            <ul className="scroll-fino max-h-48 space-y-1 overflow-y-auto">
              {d.incidencias.map((i) => (
                <li key={i.incidenciaId} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate">{TIPO_PROBLEMA[i.tipo]?.etiqueta} · <span className="text-tenue">{i.descripcion}</span></span>
                  <ChipEstado estado={i.estado} />
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="panel p-4">
          <div className="mb-3 text-[11px] text-tenue">Historial del incidente</div>
          <Historial eventos={d.historial} />
        </div>
      </div>

      {/* Flujo de Step Functions */}
      <div className="panel h-fit p-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <span className="text-[11px] text-tenue">Flujo · Step Functions</span>
          {abierto && <span className="latido size-2 rounded-full bg-acento" />}
        </div>
        <FlujoColectivo colectivo={c} />
      </div>
    </motion.section>
  );
}

function Kpi({ icono: Icono, valor, etiqueta, color }: { icono: typeof Users; valor: number; etiqueta: string; color?: string }) {
  return (
    <div className="rounded-xl bg-fondo/60 p-3">
      <Icono className="mx-auto mb-1 size-4 text-acento" style={color ? { color } : undefined} />
      <div className="cifra text-lg font-semibold" style={{ color }}>{valor}</div>
      <div className="text-[10px] text-tenue">{etiqueta}</div>
    </div>
  );
}
