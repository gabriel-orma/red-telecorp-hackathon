import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Loader2, MapPin, Navigation, Send } from "lucide-react";
import { apiIncidencias, apiPortal, type TipoProblema } from "../lib/api";
import { tokenVigente, usePerfil } from "../lib/auth";
import { TIPO_PROBLEMA } from "../lib/estados";
import { navegar } from "../lib/router";
import { cn } from "../lib/utils";
import { PortalLayout } from "../components/PortalLayout";

type Ubicacion =
  | { estado: "buscando" }
  | { estado: "gps"; lat: number; lng: number; zona: string }
  | { estado: "cuenta"; motivo: string };

/** Reporte mínimo: el usuario solo elige el tipo y describe. Ubicación automática; el resto, de su cuenta. */
export function Reportar() {
  const perfil = usePerfil();
  const [ubic, setUbic] = useState<Ubicacion>({ estado: "buscando" });
  const [tipo, setTipo] = useState<TipoProblema | null>(null);
  const [descripcion, setDescripcion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { if (!perfil) navegar("/portal/cuenta?siguiente=reportar"); }, [perfil]);

  // Ubicación automática al abrir: GPS → zona de cobertura; si no, la zona del servicio de la cuenta.
  useEffect(() => {
    if (!navigator.geolocation) return setUbic({ estado: "cuenta", motivo: "tu navegador no comparte ubicación" });
    navigator.geolocation.getCurrentPosition(
      async (p) => {
        try {
          const z = await apiIncidencias.ubicar(p.coords.latitude, p.coords.longitude);
          setUbic({ estado: "gps", lat: p.coords.latitude, lng: p.coords.longitude, zona: z.nombre });
        } catch { setUbic({ estado: "cuenta", motivo: "estás fuera de las zonas de cobertura" }); }
      },
      () => setUbic({ estado: "cuenta", motivo: "no diste permiso de ubicación" }),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }, []);

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tipo) return setError("Elige qué está fallando");
    setEnviando(true); setError(null);
    try {
      const token = await tokenVigente();
      if (!token) return navegar("/portal/cuenta?siguiente=reportar");
      const r = await apiPortal.reportar(token, {
        tipo, descripcion, ...(ubic.estado === "gps" ? { ubicacion: { lat: ubic.lat, lng: ubic.lng } } : {}),
      });
      navegar(`/portal/seguimiento/${r.incidenciaId}${r.duplicado ? "?duplicado=1" : ""}`);
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setEnviando(false); }
  };

  if (!perfil) return <PortalLayout><Loader2 className="mx-auto mt-16 size-6 animate-spin text-tenue" /></PortalLayout>;

  return (
    <PortalLayout>
      <motion.form onSubmit={enviar} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-md space-y-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">¿Qué está fallando?</h1>
          <p className="mt-1 text-sm text-tenue">Hola {perfil.nombre.split(" ")[0]}: tus datos y tu ubicación se completan solos.</p>
        </div>

        {/* Ubicación automática */}
        <div className={cn("flex items-center gap-2 rounded-xl px-3 py-2.5 text-xs ring-1",
          ubic.estado === "gps" ? "bg-normal/10 text-normal ring-normal/30" : ubic.estado === "cuenta" ? "bg-panel-2 text-texto/90 ring-borde" : "bg-panel-2 text-tenue ring-borde")}>
          {ubic.estado === "buscando" && <><Loader2 className="size-3.5 animate-spin" /> Detectando tu ubicación…</>}
          {ubic.estado === "gps" && <><Navigation className="size-3.5" /> Estás en <b>{ubic.zona}</b> · GPS</>}
          {ubic.estado === "cuenta" && <><MapPin className="size-3.5 text-acento" /> Usaremos la zona de tu servicio <span className="text-tenue">({ubic.motivo})</span></>}
        </div>

        <div className="grid grid-cols-3 gap-2">
          {(Object.keys(TIPO_PROBLEMA) as TipoProblema[]).map((t) => {
            const { etiqueta, icono: Icono } = TIPO_PROBLEMA[t];
            return (
              <button type="button" key={t} onClick={() => setTipo(t)}
                className={cn("flex flex-col items-center gap-1.5 rounded-xl border px-2 py-4 text-center text-[11px] transition",
                  tipo === t ? "border-acento bg-acento/10 text-texto shadow-[0_0_16px_#22d3ee33]" : "border-borde text-tenue hover:text-texto")}>
                <Icono className={cn("size-6", tipo === t && "text-acento")} />{etiqueta}
              </button>
            );
          })}
        </div>

        <textarea value={descripcion} onChange={(e) => setDescripcion(e.target.value)} required maxLength={2000} rows={4}
          placeholder="Cuéntanos qué pasa (ej.: desde las 9 am no cargan páginas)"
          className="w-full resize-none rounded-xl border border-borde bg-fondo px-3 py-3 text-sm outline-none focus:border-acento" />

        {error && <div className="rounded-lg bg-caida/10 px-3 py-2 text-xs text-caida ring-1 ring-caida/30">{error}</div>}

        <button type="submit" disabled={enviando || ubic.estado === "buscando"}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-acento py-3.5 text-sm font-semibold text-fondo shadow-[0_8px_30px_#22d3ee40] transition hover:brightness-110 disabled:opacity-60">
          {enviando ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />} Enviar reporte
        </button>
      </motion.form>
    </PortalLayout>
  );
}
