import { useCallback, useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, Crosshair, Globe2, Loader2, MapPin, Megaphone, Siren } from "lucide-react";
import { apiIncidencias, apiPortal, type EstadoRed } from "../lib/api";
import { ESTADO_COLECTIVO, NIVEL_RED, PRIORIDAD, TIPO_PROBLEMA, TIPO_ZONA } from "../lib/estados";
import { usePolling } from "../hooks/usePolling";
import { enlace } from "../lib/router";
import { cn, haceCuanto, numero } from "../lib/utils";
import { GraficoReportes } from "../components/GraficoReportes";
import { MapaEstado } from "../components/MapaEstado";
import { PortalLayout } from "../components/PortalLayout";

/** Página pública de estado del servicio, estilo Downdetector: ¿hay problemas ahora, en general o en mi zona? */
export function EstadoPublico() {
  const [zonaId, setZonaId] = useState<string>(() => new URLSearchParams(window.location.search).get("zona") ?? "");
  const [localizando, setLocalizando] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);
  const estado = usePolling(useCallback(() => apiPortal.estado(zonaId || undefined), [zonaId]), 15_000);
  const general = usePolling(useCallback(() => apiPortal.estado(), []), 30_000); // ranking y mapa siempre globales
  const d = estado.datos;

  useEffect(() => {
    const url = new URL(window.location.href);
    if (zonaId) url.searchParams.set("zona", zonaId); else url.searchParams.delete("zona");
    window.history.replaceState({}, "", url);
  }, [zonaId]);

  const miZona = () => {
    if (!navigator.geolocation) return setAviso("Tu navegador no permite obtener la ubicación.");
    setLocalizando(true); setAviso(null);
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        try { setZonaId((await apiIncidencias.ubicar(p.coords.latitude, p.coords.longitude)).zonaId); }
        catch { setAviso("Estás fuera de nuestras zonas de cobertura."); }
        setLocalizando(false);
      },
      () => { setAviso("No pudimos obtener tu ubicación. Elige tu zona de la lista."); setLocalizando(false); },
      { timeout: 10_000 },
    );
  };

  const zonas = general.datos?.zonas ?? [];
  const nombreZona = zonas.find((z) => z.zonaId === zonaId)?.nombre;
  const nivel = d ? NIVEL_RED[d.nivel] : null;

  return (
    <PortalLayout>
      {/* Alcance: general o una zona */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <button onClick={() => setZonaId("")}
          className={cn("flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs ring-1 transition", !zonaId ? "bg-acento/15 text-acento ring-acento/40" : "text-tenue ring-borde hover:text-texto")}>
          <Globe2 className="size-3.5" /> Toda la red
        </button>
        <button onClick={miZona} disabled={localizando}
          className={cn("flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs ring-1 transition", zonaId ? "bg-acento/15 text-acento ring-acento/40" : "text-tenue ring-borde hover:text-texto")}>
          {localizando ? <Loader2 className="size-3.5 animate-spin" /> : <Crosshair className="size-3.5" />} Mi zona
        </button>
        <select value={zonaId} onChange={(e) => setZonaId(e.target.value)}
          className="rounded-full border border-borde bg-fondo px-3 py-1.5 text-xs text-tenue outline-none focus:border-acento">
          <option value="">Elegir zona…</option>
          {zonas.map((z) => <option key={z.zonaId} value={z.zonaId}>{z.nombre}</option>)}
        </select>
        {aviso && <span className="text-[11px] text-saturada">{aviso}</span>}
      </div>

      {/* Semáforo */}
      <AnimatePresence mode="wait">
        <motion.section key={(d?.alcance ?? "") + d?.nivel} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
          className="panel overflow-hidden" style={nivel ? { borderColor: `${nivel.color}55` } : undefined}>
          <div className="flex items-center gap-4 p-5" style={nivel ? { background: `linear-gradient(120deg, ${nivel.color}26, transparent 65%)` } : undefined}>
            {nivel ? (
              <div className={cn("grid size-14 shrink-0 place-items-center rounded-2xl", d!.nivel !== "SIN_PROBLEMAS" && "latido")}
                style={{ background: `${nivel.color}22`, color: nivel.color, boxShadow: `0 0 30px ${nivel.color}44` }}>
                <nivel.icono className="size-7" />
              </div>
            ) : <Loader2 className="size-8 animate-spin text-tenue" />}
            <div className="min-w-0">
              <h1 className="text-xl font-semibold leading-tight sm:text-2xl">
                {nivel ? (zonaId ? `${nivel.corto} en ${nombreZona ?? "tu zona"}` : nivel.titulo) : "Consultando el estado…"}
              </h1>
              <p className="mt-1 text-sm text-tenue">{d?.mensaje}</p>
            </div>
          </div>
          {d && (
            <div className="grid grid-cols-3 divide-x divide-borde border-t border-borde text-center">
              <Dato valor={d.totales.ultimaHora} etiqueta="reportes en la última hora" />
              <Dato valor={Math.round(d.totales.baseHora)} etiqueta="lo normal a esta hora" />
              <Dato valor={d.totales.ultimas24h} etiqueta="reportes en 24 h" />
            </div>
          )}
        </motion.section>
      </AnimatePresence>

      {estado.error && (
        <p role="alert" className="mt-3 rounded-xl bg-saturada/10 px-4 py-2 text-xs text-saturada ring-1 ring-saturada/30">
          No pudimos actualizar el estado{estado.ultimaCarga ? ` (último dato: ${haceCuanto(new Date(estado.ultimaCarga).toISOString())})` : ""}. Reintentando…
        </p>
      )}
      {!!d?.simulacion?.colectivosAbiertos && (
        <p role="status" className="mt-3 rounded-xl bg-acento/10 px-4 py-2 text-xs text-tenue ring-1 ring-acento/30">
          Hay una <b className="text-texto">simulación en curso</b> ({d.simulacion.colectivosAbiertos} incidente{d.simulacion.colectivosAbiertos === 1 ? "" : "s"} simulado{d.simulacion.colectivosAbiertos === 1 ? "" : "s"}).
          No se cuenta aquí: este panel solo refleja reportes e incidentes reales.
        </p>
      )}

      {/* Incidentes activos */}
      {d && d.colectivos.length > 0 && (
        <section className="mt-3 space-y-2">
          {d.colectivos.map((c) => (
            <div key={c.incidenteColectivoId} className="flex items-center gap-3 rounded-xl bg-caida/10 px-4 py-3 ring-1 ring-caida/30">
              <Siren className="latido size-5 shrink-0 text-caida" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-semibold">{ESTADO_COLECTIVO[c.estado].etiqueta} · {c.nombre}</div>
                <div className="text-xs text-tenue">{c.afectados} usuarios afectados{c.antenasEnFalla ? ` · ${c.antenasEnFalla} antena(s) con falla` : ""} · desde {haceCuanto(c.detectadoEn)}</div>
              </div>
              <span className="cifra text-[10px] font-bold" style={{ color: PRIORIDAD[c.prioridad].color }}>{PRIORIDAD[c.prioridad].etiqueta.toUpperCase()}</span>
            </div>
          ))}
        </section>
      )}

      {/* Gráfico 24 h */}
      <section className="panel mt-3 p-4">
        <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold">Reportes de problemas en las últimas 24 horas{nombreZona ? ` · ${nombreZona}` : ""}</h2>
          <div className="flex items-center gap-3 text-[11px] text-tenue">
            <span className="flex items-center gap-1"><span className="h-2 w-3 rounded-sm bg-acento" /> Reportes</span>
            <span className="flex items-center gap-1"><span className="w-4 border-t-2 border-dashed border-texto/80" /> Lo normal</span>
          </div>
        </div>
        {d ? <GraficoReportes serie={d.serie} color={d.nivel === "SIN_PROBLEMAS" ? "#a78bfa" : NIVEL_RED[d.nivel].color} />
           : <div className="grid h-56 place-items-center"><Loader2 className="size-5 animate-spin text-tenue" /></div>}
        <p className="mt-2 text-[11px] text-tenue">
          Cada punto suma los reportes de 15 minutos. La línea punteada es el promedio de los últimos 7 días a la misma hora:
          un pico sobre ella indica un problema. Hay un incidente cuando 10 o más usuarios distintos de una zona reportan en menos de 24 h.
        </p>
      </section>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {/* Problemas más reportados */}
        <section className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Problemas más reportados</h2>
          {d && d.tipos.length === 0 && <p className="text-xs text-tenue">Sin reportes en las últimas 24 h.</p>}
          <ul className="space-y-3">
            {d?.tipos.map((t) => {
              const Icono = TIPO_PROBLEMA[t.tipo]?.icono ?? TIPO_PROBLEMA.OTRO.icono;
              return (
                <li key={t.tipo}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5"><Icono className="size-3.5 text-acento" />{TIPO_PROBLEMA[t.tipo]?.etiqueta ?? t.tipo}</span>
                    <span className="cifra text-tenue">{t.pct}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-fondo">
                    <motion.div className="h-full rounded-full bg-acento" initial={{ width: 0 }} animate={{ width: `${t.pct}%` }} transition={{ duration: 0.7 }} />
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        {/* Zonas con más reportes */}
        <section className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold">Zonas con más reportes (24 h)</h2>
          <ul className="space-y-1">
            {zonas.slice(0, 6).map((z) => (
              <li key={z.zonaId}>
                <button onClick={() => setZonaId(z.zonaId)}
                  className={cn("flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition hover:bg-panel-2", z.zonaId === zonaId && "bg-panel-2")}>
                  <span className="size-2 shrink-0 rounded-full" style={{ background: NIVEL_RED[z.nivel].color, boxShadow: `0 0 6px ${NIVEL_RED[z.nivel].color}` }} />
                  <span className="min-w-0 flex-1 truncate">{z.nombre} <span className="text-tenue">· {TIPO_ZONA[z.tipo]?.etiqueta}</span></span>
                  <span className="cifra font-semibold">{numero(z.total24h)}</span>
                  <ChevronRight className="size-3.5 text-tenue" />
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>

      {/* Mapa */}
      <section className="panel mt-3 p-4">
        <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold"><MapPin className="size-4 text-acento" /> Mapa de reportes</h2>
        <MapaEstado zonas={zonas} seleccion={zonaId} onZona={setZonaId} />
        <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-tenue">
          {(["SIN_PROBLEMAS", "POSIBLES_PROBLEMAS", "PROBLEMAS"] as const).map((n) => (
            <span key={n} className="flex items-center gap-1.5"><span className="size-2 rounded-full" style={{ background: NIVEL_RED[n].color }} />{NIVEL_RED[n].corto}</span>
          ))}
          <span>· más intenso = más reportes</span>
        </div>
      </section>

      {/* Llamado a la acción */}
      <a {...enlace("/portal/reportar")}
        className="sticky bottom-4 mt-5 flex items-center justify-center gap-2 rounded-2xl bg-acento py-4 text-sm font-semibold text-fondo shadow-[0_10px_40px_#7c5cff55] transition hover:brightness-110">
        <Megaphone className="size-4" /> Tengo un problema
      </a>
    </PortalLayout>
  );
}

function Dato({ valor, etiqueta }: { valor: number; etiqueta: string }) {
  return (
    <div className="px-2 py-3">
      <div className="cifra text-xl font-semibold">{numero(valor)}</div>
      <div className="text-[10px] text-tenue">{etiqueta}</div>
    </div>
  );
}

export type { EstadoRed };
