import { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Inbox, Loader2, MapPin, X } from "lucide-react";
import { apiIncidencias, apiOperador, type DetalleIncidencia, type EstadoIncidencia, type Incidencia, type Zona } from "../lib/api";
import { ESTADO, ESTADO_INCIDENCIA, ORDEN_INCIDENCIA, TIPO_PROBLEMA, TIPO_ZONA } from "../lib/estados";
import { usePolling } from "../hooks/usePolling";
import { ChipEstado, Historial, Progreso } from "../components/LineaTiempo";
import { ChipTriage } from "../components/neu/TarjetaIA";
import { cn, haceCuanto } from "../lib/utils";

export function PanelIncidencias({ zonas }: { zonas: Zona[] }) {
  const [zonaId, setZonaId] = useState("");
  const [estado, setEstado] = useState<EstadoIncidencia | "">("");
  const [seleccion, setSeleccion] = useState<string | null>(null);

  const lista = usePolling(
    useCallback(() => apiOperador.listar({ zonaId, horas: 24 * 7 }), [zonaId]),
    5000,
  );
  const todas = lista.datos?.incidencias ?? [];
  const visibles = estado ? todas.filter((i) => i.estado === estado) : todas;
  const conteo = (e: EstadoIncidencia) => todas.filter((i) => i.estado === e).length;
  const nombreZona = (id: string) => zonas.find((z) => z.zonaId === id)?.nombre ?? id;

  return (
    <main className="flex min-h-0 flex-1 gap-5">
      <section className="panel flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Filtros */}
        <div className="flex flex-wrap items-center gap-2 border-b border-borde p-3">
          <h1 className="mr-2 text-sm font-semibold">Incidencias <span className="text-tenue">· últimos 7 días</span></h1>
          <select
            value={zonaId}
            onChange={(e) => setZonaId(e.target.value)}
            className="rounded-lg border border-borde bg-fondo px-2 py-1.5 text-xs outline-none focus:border-acento"
          >
            <option value="">Todas las zonas</option>
            {zonas.map((z) => <option key={z.zonaId} value={z.zonaId}>{z.nombre}</option>)}
          </select>
          <div className="flex flex-wrap gap-1">
            <BotonFiltro activo={!estado} onClick={() => setEstado("")} etiqueta="Todas" n={todas.length} />
            {ORDEN_INCIDENCIA.map((e) => (
              <BotonFiltro key={e} activo={estado === e} onClick={() => setEstado(e)} etiqueta={ESTADO_INCIDENCIA[e].etiqueta}
                n={conteo(e)} color={ESTADO_INCIDENCIA[e].color} />
            ))}
          </div>
          {lista.error && <span className="text-xs text-caida">{lista.error}</span>}
        </div>

        {/* Lista */}
        <div className="scroll-fino min-h-0 flex-1 overflow-y-auto">
          {!lista.datos && <div className="grid h-40 place-items-center text-sm text-tenue"><Loader2 className="size-5 animate-spin" /></div>}
          {lista.datos && !visibles.length && (
            <div className="grid h-60 place-items-center text-center text-sm text-tenue">
              <div><Inbox className="mx-auto mb-2 size-8 opacity-50" />No hay incidencias con estos filtros.<br />Crea una desde el <a href="/portal" className="text-acento">portal del usuario</a>.</div>
            </div>
          )}
          <ul className="divide-y divide-borde/60">
            {visibles.map((i) => <FilaIncidencia key={i.incidenciaId} i={i} zona={nombreZona(i.zonaId)}
              activa={i.incidenciaId === seleccion} onClick={() => setSeleccion(i.incidenciaId)} />)}
          </ul>
        </div>
      </section>

      <AnimatePresence>
        {seleccion && <Detalle key={seleccion} id={seleccion} onCerrar={() => setSeleccion(null)} onCambio={lista.refrescar} />}
      </AnimatePresence>
    </main>
  );
}

function BotonFiltro({ activo, onClick, etiqueta, n, color }: { activo: boolean; onClick: () => void; etiqueta: string; n: number; color?: string }) {
  return (
    <button onClick={onClick}
      className={cn("flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] ring-1 transition", activo ? "bg-panel-2 text-texto ring-acento/50" : "text-tenue ring-borde hover:text-texto")}>
      {color && <span className="size-1.5 rounded-full" style={{ background: color }} />}
      {etiqueta} <span className="cifra opacity-70">{n}</span>
    </button>
  );
}

function FilaIncidencia({ i, zona, activa, onClick }: { i: Incidencia; zona: string; activa: boolean; onClick: () => void }) {
  const Icono = TIPO_PROBLEMA[i.tipo]?.icono ?? TIPO_PROBLEMA.OTRO.icono;
  return (
    <li>
      <button onClick={onClick} className={cn("flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-panel-2/60", activa && "bg-panel-2")}>
        <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-acento/10 text-acento"><Icono className="size-4" /></div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{TIPO_PROBLEMA[i.tipo]?.etiqueta ?? i.tipo}</span>
            <span className="cifra hidden text-[10px] text-tenue xl:inline">{i.incidenciaId}</span>
          </div>
          <div className="truncate text-xs text-tenue">{i.reporte.descripcion}</div>
        </div>
        <div className="hidden w-44 shrink-0 truncate text-xs text-tenue lg:block"><MapPin className="mr-1 inline size-3" />{zona}</div>
        <div className="hidden w-20 shrink-0 text-right text-[11px] text-tenue sm:block">{haceCuanto(i.creadaEn)}</div>
        <div className="w-28 shrink-0 text-right"><ChipEstado estado={i.estado} /></div>
      </button>
    </li>
  );
}

function Detalle({ id, onCerrar, onCambio }: { id: string; onCerrar: () => void; onCambio: () => void }) {
  const det = usePolling<DetalleIncidencia>(useCallback(() => apiOperador.obtener(id), [id]), 4000);
  const [comentario, setComentario] = useState("");
  const [enviando, setEnviando] = useState<EstadoIncidencia | null>(null);
  const [error, setError] = useState<string | null>(null);
  const d = det.datos;

  const cambiar = async (estado: EstadoIncidencia) => {
    setEnviando(estado); setError(null);
    try {
      await apiIncidencias.cambiarEstado(id, estado, comentario);
      setComentario("");
      await det.refrescar(); onCambio();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setEnviando(null); }
  };

  return (
    <motion.aside initial={{ opacity: 0, x: 30 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 30 }}
      className="panel scroll-fino fixed inset-x-3 bottom-3 top-16 z-20 flex flex-col gap-4 overflow-y-auto p-4 md:static md:w-[400px] md:shrink-0">
      <div className="flex items-start justify-between">
        <div>
          <div className="cifra text-sm font-semibold">{id}</div>
          {d && <div className="text-xs text-tenue">{TIPO_PROBLEMA[d.incidencia.tipo]?.etiqueta} · {d.zona.nombre}</div>}
        </div>
        <button onClick={onCerrar} className="rounded-md p-1 text-tenue hover:bg-panel-2 hover:text-texto" aria-label="Cerrar"><X className="size-4" /></button>
      </div>
      {!d && <Loader2 className="mx-auto size-5 animate-spin text-tenue" />}
      {d && (<>
        <Progreso estado={d.incidencia.estado} />

        <div className="rounded-xl bg-fondo/60 p-3 text-sm">
          <p className="whitespace-pre-wrap">{d.incidencia.reporte.descripcion}</p>
          {d.incidencia.iaTriage && <ChipTriage triage={d.incidencia.iaTriage} />}
          <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] text-tenue">
            <dt>Usuario</dt><dd className="cifra text-texto">{d.incidencia.reporte.usuarioId}</dd>
            <dt>Servicio</dt><dd className="cifra text-texto">{d.incidencia.reporte.numeroServicio}</dd>
            <dt>Contacto</dt><dd className="truncate text-texto">{d.incidencia.reporte.email ?? d.incidencia.reporte.telefonoContacto}</dd>
            <dt>Ocurrió</dt><dd className="text-texto">{new Date(d.incidencia.reporte.fechaHoraIncidente).toLocaleString("es-PE")}</dd>
          </dl>
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <Dato etiqueta="Red de la zona" valor={ESTADO[d.zona.estadoRed].etiqueta} color={ESTADO[d.zona.estadoRed].color} />
          <Dato etiqueta="Reportes 24 h" valor={String(d.zona.reportesActivos24h)} />
          <Dato etiqueta="Tipo de zona" valor={TIPO_ZONA[d.zona.tipo]?.etiqueta ?? "—"} />
        </div>

        <div>
          <div className="mb-1.5 text-[11px] text-tenue">Cambiar estado</div>
          {d.incidencia.transicionesPermitidas.length === 0
            ? <div className="text-xs text-tenue">La incidencia está cerrada.</div>
            : (<>
              <input value={comentario} onChange={(e) => setComentario(e.target.value)} placeholder="Comentario (opcional)"
                className="mb-2 w-full rounded-lg border border-borde bg-fondo px-3 py-2 text-xs outline-none focus:border-acento" />
              <div className="flex flex-wrap gap-1.5">
                {d.incidencia.transicionesPermitidas.map((e) => (
                  <button key={e} disabled={!!enviando} onClick={() => cambiar(e)}
                    className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ring-1 transition hover:brightness-125 disabled:opacity-50"
                    style={{ color: ESTADO_INCIDENCIA[e].color, background: `${ESTADO_INCIDENCIA[e].color}14`, ["--tw-ring-color" as string]: `${ESTADO_INCIDENCIA[e].color}55` }}>
                    {enviando === e && <Loader2 className="size-3 animate-spin" />}
                    {ESTADO_INCIDENCIA[e].etiqueta}
                  </button>
                ))}
              </div>
            </>)}
          {error && <div className="mt-2 text-xs text-caida">{error}</div>}
        </div>

        <div>
          <div className="mb-2 text-[11px] text-tenue">Historial</div>
          <Historial eventos={d.historial} />
        </div>
      </>)}
    </motion.aside>
  );
}

function Dato({ etiqueta, valor, color }: { etiqueta: string; valor: string; color?: string }) {
  return (
    <div className="rounded-lg bg-fondo/60 px-2 py-2">
      <div className="text-[10px] text-tenue">{etiqueta}</div>
      <div className="text-xs font-semibold" style={{ color }}>{valor}</div>
    </div>
  );
}
