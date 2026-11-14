import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Flame, Siren, TowerControl, Zap } from "lucide-react";
import { apiEscenarios, apiLineaTiempo, type Antena, type Colectivo, type DatosLineaTiempo, type EstadoEscenario, type Zona } from "../lib/api";
import { ESTADO_COLECTIVO, ES_FALLA, GRAVEDAD, PRIORIDAD } from "../lib/estados";
import { colectivosEn, estadoAntenaEn, indexar, reportesEn, ventanaCalor } from "../lib/lineaTiempo";
import { usePolling } from "../hooks/usePolling";
import { useAlCambiar } from "../lib/tiempoReal";
import { navegar } from "../lib/router";
import { cn } from "../lib/utils";
import { MapaRed } from "../components/MapaRed";
import { ShellNeu } from "../components/neu/ShellNeu";
import { PaletaComandos } from "../components/neu/PaletaComandos";
import { ControlEscenario } from "../components/neu/ControlEscenario";
import { EditorTiempo } from "../components/neu/EditorTiempo";
import { Cifra } from "../components/neu/Piezas";
import { PALETA_MAPA_NEU } from "../components/neu/paleta";

interface Props { antenas: Antena[]; zonas: Zona[]; colectivosActivos: number; enVivo: boolean; refrescarRed: () => void }

/** Línea de tiempo del centro de control: arrastra el cabezal y el mapa muestra la red en ese instante. */
export function LineaTiempoNeu({ antenas, zonas, colectivosActivos, enVivo: apiViva, refrescarRed }: Props) {
  const [horas, setHoras] = useState(1);
  const [vivo, setVivo] = useState(true); // el cabezal sigue al presente y los datos se actualizan solos
  const [reproduciendo, setReproduciendo] = useState(false);
  const [velocidad, setVelocidad] = useState(60);
  const [ahora, setAhora] = useState(() => Date.now());
  const [t, setT] = useState(() => Date.now());
  const [marco, setMarco] = useState<{ desde: number; hasta: number } | null>(null); // ventana congelada fuera de "en vivo"
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [buscar, setBuscar] = useState(false);

  // Datos: en vivo se recargan con cada aviso del WebSocket (como mucho cada 2,5 s). Fuera de "en vivo" se congelan:
  // así los clips no se desplazan bajo el cursor mientras el operador revisa el pasado.
  const vivoRef = useRef(vivo);
  vivoRef.current = vivo;
  const ultimo = useRef<{ horas: number; datos: DatosLineaTiempo } | null>(null);
  const datos = usePolling(useCallback(async () => {
    const previo = ultimo.current;
    if (previo && previo.horas === horas && !vivoRef.current) return previo.datos;
    const d = await apiLineaTiempo.obtener(horas);
    ultimo.current = { horas, datos: d };
    return d;
  }, [horas]), 15_000);
  useEffect(() => { datos.refrescar(); }, [horas]); // eslint-disable-line react-hooks/exhaustive-deps
  useAlCambiar(["antenas", "colectivos", "incidencias"], () => { if (vivoRef.current) datos.refrescar(); }, 2500);

  const escenario = usePolling<EstadoEscenario>(useCallback(() => apiEscenarios.estado(), []), 3000);
  const linea = useMemo(() => (datos.datos && zonas.length ? indexar(datos.datos, zonas) : null), [datos.datos, zonas]);

  // Ventana visible: en vivo termina "ahora" y se desliza; si no, queda fija.
  const desde = vivo || !marco ? ahora - horas * 3600_000 : marco.desde;
  const hasta = vivo || !marco ? ahora : marco.hasta;

  // Reloj: en vivo el cabezal es el presente; reproduciendo avanza `velocidad` veces más rápido que el tiempo real.
  useEffect(() => {
    let frame = 0, previo = performance.now(), ultimoVivo = 0;
    const paso = (ms: number) => {
      const dt = ms - previo;
      previo = ms;
      if (vivoRef.current) {
        // En vivo basta con 4 actualizaciones por segundo (el mapa no necesita 60 fps para "el presente").
        if (ms - ultimoVivo >= 250) { ultimoVivo = ms; const n = Date.now(); setAhora(n); setT(n); }
      } else if (reproduciendoRef.current) {
        setT((tt) => {
          const nuevo = tt + dt * velocidadRef.current;
          if (nuevo >= hastaRef.current) { queueMicrotask(irEnVivo); return hastaRef.current; }
          return nuevo;
        });
      }
      frame = requestAnimationFrame(paso);
    };
    frame = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(frame);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const reproduciendoRef = useRef(reproduciendo); reproduciendoRef.current = reproduciendo;
  const velocidadRef = useRef(velocidad); velocidadRef.current = velocidad;
  const hastaRef = useRef(hasta); hastaRef.current = hasta;

  const congelar = () => {
    if (!vivoRef.current) return;
    const n = Date.now();
    setMarco({ desde: n - horas * 3600_000, hasta: n });
    setVivo(false);
  };
  const irEnVivo = () => { setReproduciendo(false); setVivo(true); setMarco(null); datos.refrescar(); };
  const moverCabezal = (nuevo: number) => { congelar(); setT(nuevo); };
  const alternarReproduccion = (r: boolean) => {
    if (r) {
      congelar();
      // Desde el final (o en vivo) no hay nada que reproducir: empezar desde el inicio de la ventana.
      if (vivoRef.current || t >= hasta - 1000) setT(desde);
    }
    setReproduciendo(r);
  };
  const cambiarHoras = (h: number) => { setHoras(h); setVivo(true); setMarco(null); setReproduciendo(false); };

  // Simulación acelerada en curso → ventana de 15 min y en vivo, para verla "en directo".
  const acelerada = !!escenario.datos?.activo && escenario.datos.tipo === "ACELERADA";
  useEffect(() => { if (acelerada) cambiarHoras(0.25); }, [acelerada]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- Estado de la red en el instante del cabezal ----------
  // useDeferredValue: el cabezal se mueve a 60 fps y el mapa se actualiza en cuanto puede, sin trabar el arrastre.
  const tm = useDeferredValue(t);
  const ventana = ventanaCalor(hasta - desde);
  const red = useMemo(() => {
    if (!linea) return null;
    const ant = antenas.map((a) => ({ ...a, estado: linea.antenas.has(a.antenaId) ? estadoAntenaEn(linea, a.antenaId, tm) : a.estado }));
    const porId = new Map(ant.map((a) => [a.antenaId, a.estado]));
    const zon = zonas.map((z) => {
      const estados = z.antenas.map((a) => porId.get(a.antenaId) ?? "SIN_DATOS");
      return { ...z, estado: estados.reduce((p, e) => (GRAVEDAD[e] > GRAVEDAD[p] ? e : p), "SIN_DATOS" as typeof estados[number]) };
    });
    const abiertos = colectivosEn(linea, tm).sort((a, b) => b.afectados - a.afectados);
    const cols = abiertos.map((c) => ({ incidenteColectivoId: c.id, zonaId: c.zonaId, estado: c.estadoEn, prioridad: c.prioridadEn }) as unknown as Colectivo);
    const puntos = reportesEn(linea, tm, ventana);
    return { ant, zon, cols, abiertos, puntos, enFalla: ant.filter((a) => ES_FALLA(a.estado)).length };
  }, [linea, antenas, zonas, tm, ventana]);

  const zonaSel = useMemo(() => {
    const c = linea?.colectivos.find((x) => x.id === seleccion);
    return c ? zonas.find((z) => z.zonaId === c.zonaId) ?? null : null;
  }, [seleccion, linea, zonas]);

  return (
    <ShellNeu titulo="Línea de tiempo" enVivo={apiViva} colectivosActivos={colectivosActivos} onBuscar={() => setBuscar(true)}
      acciones={<ControlEscenario zonas={zonas} onCambio={refrescarRed} />}>
      <PaletaComandos abierta={buscar} onAbrir={() => setBuscar(true)} onCerrar={() => setBuscar(false)} zonas={zonas} antenas={antenas}
        onZona={(z) => navegar(`/?zona=${z.zonaId}`)} onAntena={(a) => navegar(`/?antena=${a.antenaId}`)} />

      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[minmax(0,1fr)_280px]">
        {/* Monitor: el mapa en el instante del cabezal */}
        <div className="neu-hundido relative min-h-[46vh] overflow-hidden p-1.5">
          <div className="relative h-full min-h-[46vh] overflow-hidden rounded-[13px]">
            <MapaRed antenas={red?.ant ?? antenas} zonas={red?.zon ?? zonas} colectivos={red?.cols ?? []} reportes={[]}
              puntosCalor={red?.puntos ?? []} seleccion={null} onSeleccionar={() => {}} enfocarZona={zonaSel} paleta={PALETA_MAPA_NEU} />

            <div className="pointer-events-none absolute left-4 top-4 z-10 flex flex-wrap gap-2">
              <span className={cn("neu-chico flex items-center gap-2 px-3 py-2 text-[11px] font-semibold",
                vivo ? "text-caida" : reproduciendo ? "text-acento" : "text-tenue")}>
                <span className={cn("size-2 rounded-full", vivo ? "latido bg-caida" : reproduciendo ? "bg-acento" : "bg-tenue/60")} />
                {vivo ? "EN VIVO" : reproduciendo ? `REPRODUCIENDO ${velocidad}×` : "PAUSA"}
              </span>
              <Dato icono={Flame} color="#f472b6" valor={red?.puntos.length ?? 0} texto={`reportes · últimos ${Math.round(ventana / 60_000)} min`} />
              <Dato icono={TowerControl} color="#f0506e" valor={red?.enFalla ?? 0} texto="antenas en falla" />
              <Dato icono={Siren} color="#a78bfa" valor={red?.abiertos.length ?? 0} texto="incidentes abiertos" />
            </div>

            <AnimatePresence>
              {escenario.datos?.activo && escenario.datos.narrativa && (
                <motion.div key={escenario.datos.narrativa} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.2 }}
                  className="neu-chico pointer-events-none absolute bottom-4 left-1/2 z-10 flex -translate-x-1/2 items-center gap-2 px-4 py-2 text-xs">
                  <Zap className="size-3.5 text-[#e05ab0]" /> {escenario.datos.narrativa}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* "En este instante": la cola de atención tal como estaba en t */}
        <aside className="neu scroll-fino flex min-h-0 flex-col overflow-y-auto p-3 lg:max-h-none">
          <div className="px-2 pb-2 pt-1 text-sm text-tenue">En este instante</div>
          <ol className="space-y-1">
            <AnimatePresence initial={false}>
              {(red?.abiertos ?? []).map((c) => (
                <motion.li key={c.id} layout="position" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  transition={{ duration: 0.15, layout: { type: "spring", stiffness: 500, damping: 40 } }}>
                  <button onClick={() => setSeleccion(c.id)} onDoubleClick={() => navegar(`/colectivos?id=${c.id}`)}
                    className={cn("flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-panel-2", seleccion === c.id && "bg-panel-2")}>
                    <span className="size-2.5 shrink-0 rounded-full" style={{ background: PRIORIDAD[c.prioridadEn].color }} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{c.zonaNombre}</span>
                      <span className="block truncate text-[11px]" style={{ color: ESTADO_COLECTIVO[c.estadoEn].color }}>{ESTADO_COLECTIVO[c.estadoEn].etiqueta}</span>
                    </span>
                    <span className="text-[11px] font-semibold" style={{ color: PRIORIDAD[c.prioridadEn].color }}>{PRIORIDAD[c.prioridadEn].etiqueta}</span>
                  </button>
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>
          {!red?.abiertos.length && <p className="px-2 py-6 text-center text-xs text-tenue">Sin incidentes abiertos en este momento.</p>}
          <p className="mt-auto px-2 pt-4 text-[10px] leading-relaxed text-tenue">
            Arrastra el cabezal o usa ← →. Espacio reproduce. Un clic en un incidente lo enfoca; doble clic abre su detalle.
          </p>
        </aside>
      </div>

      <EditorTiempo linea={linea} desde={desde} hasta={hasta} t={t} onT={moverCabezal}
        reproduciendo={reproduciendo} onReproducir={alternarReproduccion} velocidad={velocidad} onVelocidad={setVelocidad}
        horas={horas} onHoras={cambiarHoras} enVivo={vivo} onEnVivo={irEnVivo} cargando={!datos.datos}
        seleccion={seleccion} onColectivo={(id) => {
          setSeleccion(id);
          const c = linea?.colectivos.find((x) => x.id === id);
          if (c) moverCabezal(Math.min(Math.max(c.inicio, desde), hasta));
        }} />
    </ShellNeu>
  );
}

function Dato({ icono: Icono, color, valor, texto }: { icono: typeof Flame; color: string; valor: number; texto: string }) {
  return (
    <span className="neu-chico flex items-center gap-2 px-3 py-2 text-[11px]">
      <Icono className="size-3.5" style={{ color }} />
      <Cifra valor={valor} className="font-semibold" />
      <span className="text-tenue">{texto}</span>
    </span>
  );
}
