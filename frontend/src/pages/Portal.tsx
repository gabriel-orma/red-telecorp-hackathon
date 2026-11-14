import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronRight, Crosshair, Loader2, MapPin, Send, ShieldCheck } from "lucide-react";
import { api, apiIncidencias, type Reporte, type TipoProblema, type Zona, type ZonaUbicada } from "../lib/api";
import { TIPO_PROBLEMA, TIPO_ZONA } from "../lib/estados";
import { enlace, navegar } from "../lib/router";
import { cn, haceCuanto } from "../lib/utils";
import { MapaSelector } from "../components/MapaSelector";
import { PortalLayout, guardarReporte, misReportes } from "../components/PortalLayout";

const CLAVE_DATOS = "telecorp.datosUsuario";
const ahoraLocal = () => {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
};

type Datos = { usuarioId: string; nombre: string; numeroServicio: string; email: string; telefonoContacto: string };

function datosGuardados(): Datos {
  const vacio = { usuarioId: "", nombre: "", numeroServicio: "", email: "", telefonoContacto: "" };
  try { return { ...vacio, ...JSON.parse(localStorage.getItem(CLAVE_DATOS) ?? "{}") }; } catch { return vacio; }
}

export function Portal() {
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [datos, setDatos] = useState<Datos>(datosGuardados);
  const [punto, setPunto] = useState<{ lat: number; lng: number } | null>(null);
  const [zona, setZona] = useState<ZonaUbicada | null>(null);
  const [zonaManual, setZonaManual] = useState("");
  const [avisoUbicacion, setAvisoUbicacion] = useState<string | null>(null);
  const [localizando, setLocalizando] = useState(false);
  const [tipo, setTipo] = useState<TipoProblema | null>(null);
  const [cuando, setCuando] = useState(ahoraLocal);
  const [descripcion, setDescripcion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errores, setErrores] = useState<string[]>([]);
  const historialLocal = misReportes();

  useEffect(() => { api.zonas().then((r) => setZonas(r.zonas)).catch(() => {}); }, []);

  // Cada vez que cambia el punto, el backend decide a qué zona pertenece.
  useEffect(() => {
    if (!punto) return;
    setAvisoUbicacion(null);
    apiIncidencias.ubicar(punto.lat, punto.lng)
      .then((z) => { setZona(z); setZonaManual(""); })
      .catch((e) => { setZona(null); setAvisoUbicacion(e.message); });
  }, [punto]);

  const usarMiUbicacion = () => {
    if (!navigator.geolocation) return setAvisoUbicacion("Tu navegador no permite obtener la ubicación.");
    setLocalizando(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { setPunto({ lat: p.coords.latitude, lng: p.coords.longitude }); setLocalizando(false); },
      () => { setAvisoUbicacion("No pudimos obtener tu ubicación. Marca el punto en el mapa o elige tu zona."); setLocalizando(false); },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  };

  const zonaId = zona?.zonaId ?? zonaManual;
  const campo = (k: keyof Datos) => ({
    value: datos[k],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setDatos({ ...datos, [k]: e.target.value }),
  });

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrores([]);
    if (!tipo) return setErrores(["Elige el tipo de problema"]);
    if (!zonaId) return setErrores(["Indica tu ubicación o elige tu zona"]);
    setEnviando(true);
    try { localStorage.setItem(CLAVE_DATOS, JSON.stringify(datos)); } catch { /* sin almacenamiento */ }
    const reporte: Reporte = {
      ...datos,
      email: datos.email || undefined,
      telefonoContacto: datos.telefonoContacto || undefined,
      zonaId,
      ubicacion: punto ?? undefined,
      fechaHoraIncidente: new Date(cuando).toISOString(),
      tipo,
      descripcion,
    };
    try {
      const r = await apiIncidencias.reportar(reporte);
      guardarReporte(r.incidenciaId, tipo);
      navegar(`/portal/seguimiento/${r.incidenciaId}${r.duplicado ? "?duplicado=1" : ""}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrores([msg]);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <PortalLayout>
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-semibold tracking-tight">¿Problemas con tu servicio?</h1>
        <p className="mt-1 text-sm text-tenue">Cuéntanos qué pasa. Si otros vecinos reportan lo mismo, lo detectamos como una falla de zona y te avisamos.</p>
      </motion.div>

      {historialLocal.length > 0 && (
        <section className="panel mt-5 p-3">
          <div className="mb-1 px-1 text-[11px] uppercase tracking-wider text-tenue">Tus reportes</div>
          {historialLocal.slice(0, 3).map((r) => (
            <a key={r.id} {...enlace(`/portal/seguimiento/${r.id}`)} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-panel-2">
              <span>{TIPO_PROBLEMA[r.tipo as TipoProblema]?.etiqueta ?? r.tipo} <span className="cifra text-[10px] text-tenue">{r.id}</span></span>
              <span className="flex items-center gap-1 text-xs text-tenue">{haceCuanto(r.creado)} <ChevronRight className="size-3.5" /></span>
            </a>
          ))}
        </section>
      )}

      <form onSubmit={enviar} className="mt-5 space-y-4">
        <Paso n={1} titulo="¿Qué está fallando?">
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
            {(Object.keys(TIPO_PROBLEMA) as TipoProblema[]).map((t) => {
              const { etiqueta, icono: Icono } = TIPO_PROBLEMA[t];
              return (
                <button type="button" key={t} onClick={() => setTipo(t)}
                  className={cn("flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center text-[11px] transition",
                    tipo === t ? "border-acento bg-acento/10 text-texto shadow-[0_0_16px_#22d3ee33]" : "border-borde text-tenue hover:text-texto")}>
                  <Icono className={cn("size-5", tipo === t && "text-acento")} />
                  {etiqueta}
                </button>
              );
            })}
          </div>
          <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} required maxLength={2000} rows={3}
            placeholder="Describe lo que pasa (ej.: desde las 9 am no cargan páginas y no puedo hacer llamadas)"
            className="mt-3 w-full resize-none rounded-xl border border-borde bg-fondo px-3 py-2.5 text-sm outline-none focus:border-acento" />
          <label className="mt-2 flex items-center justify-between gap-3 text-xs text-tenue">
            ¿Desde cuándo?
            <input type="datetime-local" value={cuando} max={ahoraLocal()} onChange={(e) => setCuando(e.target.value)}
              className="rounded-lg border border-borde bg-fondo px-2 py-1.5 text-xs text-texto outline-none focus:border-acento" />
          </label>
        </Paso>

        <Paso n={2} titulo="¿Dónde estás?">
          <button type="button" onClick={usarMiUbicacion} disabled={localizando}
            className="mb-2 flex w-full items-center justify-center gap-2 rounded-xl bg-acento/15 py-2.5 text-sm font-medium text-acento ring-1 ring-acento/40 transition hover:bg-acento/25">
            {localizando ? <Loader2 className="size-4 animate-spin" /> : <Crosshair className="size-4" />}
            Usar mi ubicación
          </button>
          <MapaSelector zonas={zonas} punto={punto} onPunto={setPunto} />
          <p className="mt-1.5 text-[11px] text-tenue">o toca el mapa / arrastra el pin para marcar el lugar exacto.</p>
          {zona && (
            <div className="mt-2 flex items-center gap-2 rounded-lg bg-normal/10 px-3 py-2 text-xs text-normal ring-1 ring-normal/30">
              <MapPin className="size-3.5" /> Estás en <b>{zona.nombre}</b> · {TIPO_ZONA[zona.tipo].etiqueta}
            </div>
          )}
          {avisoUbicacion && <div className="mt-2 text-xs text-saturada">{avisoUbicacion}</div>}
          {!zona && (
            <select value={zonaManual} onChange={(e) => setZonaManual(e.target.value)}
              className="mt-2 w-full rounded-xl border border-borde bg-fondo px-3 py-2.5 text-sm outline-none focus:border-acento">
              <option value="">…o elige tu zona de la lista</option>
              {zonas.map((z) => <option key={z.zonaId} value={z.zonaId}>{z.nombre}</option>)}
            </select>
          )}
        </Paso>

        <Paso n={3} titulo="Tus datos">
          <div className="grid gap-2 sm:grid-cols-2">
            <Campo etiqueta="DNI / CE" requerido inputMode="numeric" {...campo("usuarioId")} />
            <Campo etiqueta="Nombre" {...campo("nombre")} />
            <Campo etiqueta="Número del servicio" requerido inputMode="tel" placeholder="9XX XXX XXX" {...campo("numeroServicio")} />
            <Campo etiqueta="Celular para avisos" inputMode="tel" placeholder="+51 9XX XXX XXX" {...campo("telefonoContacto")} />
            <div className="sm:col-span-2"><Campo etiqueta="Correo para avisos" type="email" {...campo("email")} /></div>
          </div>
          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-tenue"><ShieldCheck className="size-3.5" /> Solo usamos tus datos para avisarte sobre esta incidencia.</p>
        </Paso>

        {errores.length > 0 && (
          <ul className="rounded-xl bg-caida/10 px-4 py-3 text-sm text-caida ring-1 ring-caida/30">
            {errores.map((e) => <li key={e}>• {e}</li>)}
          </ul>
        )}

        <button type="submit" disabled={enviando}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-acento py-3.5 text-sm font-semibold text-fondo shadow-[0_8px_30px_#22d3ee40] transition hover:brightness-110 disabled:opacity-60">
          {enviando ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />} Enviar reporte
        </button>
      </form>
    </PortalLayout>
  );
}

function Paso({ n, titulo, children }: { n: number; titulo: string; children: React.ReactNode }) {
  return (
    <section className="panel p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <span className="cifra grid size-6 place-items-center rounded-full bg-acento/15 text-xs text-acento">{n}</span>{titulo}
      </h2>
      {children}
    </section>
  );
}

function Campo({ etiqueta, requerido, ...props }: { etiqueta: string; requerido?: boolean } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] text-tenue">{etiqueta}{requerido && <span className="text-acento"> *</span>}</span>
      <input required={requerido} {...props}
        className="w-full rounded-xl border border-borde bg-fondo px-3 py-2.5 text-sm outline-none transition focus:border-acento" />
    </label>
  );
}
