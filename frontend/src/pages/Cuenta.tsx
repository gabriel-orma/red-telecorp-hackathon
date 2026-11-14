import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ChevronRight, Crosshair, Loader2, LogOut, MapPin, Smartphone } from "lucide-react";
import { api, apiIncidencias, apiPortal, type MiReporte, type Zona } from "../lib/api";
import { cerrarSesion, iniciarSesion, registrar, tokenVigente, usePerfil, type Perfil } from "../lib/auth";
import { TIPO_PROBLEMA } from "../lib/estados";
import { enlace, navegar } from "../lib/router";
import { cn, haceCuanto } from "../lib/utils";
import { ChipEstado } from "../components/LineaTiempo";
import { PortalLayout } from "../components/PortalLayout";

const destinoTrasLogin = () => new URLSearchParams(window.location.search).get("siguiente") ?? "";

export function Cuenta() {
  const perfil = usePerfil();
  return <PortalLayout>{perfil ? <MiCuenta perfil={perfil} /> : <Acceso />}</PortalLayout>;
}

// ---------------- Sin sesión: ingresar o crear cuenta ----------------
function Acceso() {
  const [modo, setModo] = useState<"ingresar" | "registrar">("ingresar");
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [f, setF] = useState({ email: "", password: "", nombre: "", dni: "", numeroServicio: "", telefono: "+51", zonaId: "", avisosEmail: true });
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [localizando, setLocalizando] = useState(false);

  useEffect(() => { api.zonas().then((r) => setZonas(r.zonas)).catch(() => {}); }, []);
  const campo = (k: keyof typeof f) => ({
    value: String(f[k]), onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value }),
  });

  const detectarZona = () => {
    setLocalizando(true);
    navigator.geolocation?.getCurrentPosition(
      async (p) => {
        try { setF((x) => ({ ...x, zonaId: "" })); const z = await apiIncidencias.ubicar(p.coords.latitude, p.coords.longitude); setF((x) => ({ ...x, zonaId: z.zonaId })); }
        catch { setError("Tu ubicación está fuera de nuestras zonas: elige la zona de tu servicio en la lista."); }
        setLocalizando(false);
      },
      () => { setError("No pudimos obtener tu ubicación: elige la zona en la lista."); setLocalizando(false); },
      { timeout: 10_000 },
    );
  };

  const enviar = async (e: React.FormEvent) => {
    e.preventDefault();
    setEnviando(true); setError(null);
    try {
      if (modo === "ingresar") await iniciarSesion(f.email.trim(), f.password);
      else {
        const telefono = f.telefono.replace(/[\s-]/g, "");
        const datos: Perfil & { password: string } = {
          email: f.email.trim(), password: f.password, nombre: f.nombre.trim(), dni: f.dni.trim(),
          numeroServicio: f.numeroServicio.trim(), telefono: telefono.length > 4 ? telefono : undefined,
          zonaId: f.zonaId, avisosEmail: f.avisosEmail ? "1" : "0",
        };
        await registrar(datos);
      }
      const destino = destinoTrasLogin();
      if (destino) navegar(`/portal/${destino}`);
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setEnviando(false); }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mx-auto max-w-md">
      <h1 className="text-2xl font-semibold tracking-tight">{modo === "ingresar" ? "Ingresa a tu cuenta" : "Crea tu cuenta"}</h1>
      <p className="mt-1 text-sm text-tenue">
        {modo === "ingresar" ? "Con tu cuenta reportas un problema en dos toques: tipo y descripción." : "Tus datos se usan para identificar tu servicio y avisarte sobre las fallas."}
      </p>
      <div className="mt-4 flex rounded-xl bg-fondo p-1 ring-1 ring-borde">
        {(["ingresar", "registrar"] as const).map((m) => (
          <button key={m} onClick={() => { setModo(m); setError(null); }}
            className={cn("flex-1 rounded-lg py-2 text-xs font-medium", modo === m ? "bg-panel-2 text-texto" : "text-tenue")}>
            {m === "ingresar" ? "Ingresar" : "Crear cuenta"}
          </button>
        ))}
      </div>

      <form onSubmit={enviar} className="panel mt-3 space-y-3 p-4">
        {modo === "registrar" && (<>
          <Campo etiqueta="Nombre completo" required {...campo("nombre")} />
          <div className="grid grid-cols-2 gap-2">
            <Campo etiqueta="DNI / CE" required inputMode="numeric" pattern="[0-9]{8,12}" title="8 a 12 dígitos" {...campo("dni")} />
            <Campo etiqueta="N.° del servicio" required inputMode="tel" {...campo("numeroServicio")} />
          </div>
          <Campo etiqueta="Celular (para avisos)" inputMode="tel" placeholder="+51999888777" {...campo("telefono")} />
          <label className="block">
            <span className="mb-1 block text-[11px] text-tenue">Zona de tu servicio <span className="text-acento">*</span>
              <span className="text-tenue"> · se usa si tu GPS no está disponible al reportar</span></span>
            <div className="flex gap-2">
              <select required {...campo("zonaId")} className="min-w-0 flex-1 rounded-xl border border-borde bg-fondo px-3 py-2.5 text-sm outline-none focus:border-acento">
                <option value="">Elige tu zona…</option>
                {zonas.map((z) => <option key={z.zonaId} value={z.zonaId}>{z.nombre}</option>)}
              </select>
              <button type="button" onClick={detectarZona} title="Detectar con mi ubicación"
                className="grid w-11 place-items-center rounded-xl bg-acento/15 text-acento ring-1 ring-acento/40">
                {localizando ? <Loader2 className="size-4 animate-spin" /> : <Crosshair className="size-4" />}
              </button>
            </div>
          </label>
        </>)}
        <Campo etiqueta="Correo" type="email" required autoComplete="email" {...campo("email")} />
        <Campo etiqueta="Contraseña" type="password" required minLength={8} autoComplete={modo === "ingresar" ? "current-password" : "new-password"}
          placeholder={modo === "registrar" ? "Mín. 8 caracteres, con minúsculas y números" : ""} {...campo("password")} />
        {modo === "registrar" && (
          <label className="flex cursor-pointer items-start gap-2 text-xs">
            <input type="checkbox" checked={f.avisosEmail} onChange={(e) => setF({ ...f, avisosEmail: e.target.checked })} className="mt-0.5 accent-[#a78bfa]" />
            <span>Avisarme por correo cuando haya una falla en mi zona <span className="text-tenue">(AWS te enviará un correo para confirmar)</span></span>
          </label>
        )}
        {error && <div className="rounded-lg bg-caida/10 px-3 py-2 text-xs text-caida ring-1 ring-caida/30">{error}</div>}
        <button type="submit" disabled={enviando}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-acento py-3 text-sm font-semibold text-fondo transition hover:brightness-110 disabled:opacity-60">
          {enviando && <Loader2 className="size-4 animate-spin" />}{modo === "ingresar" ? "Ingresar" : "Crear cuenta"}
        </button>
      </form>
    </motion.div>
  );
}

// ---------------- Con sesión: perfil + mis reportes ----------------
function MiCuenta({ perfil }: { perfil: Perfil }) {
  const [reportes, setReportes] = useState<MiReporte[] | null>(null);
  const [zonas, setZonas] = useState<Zona[]>([]);
  const cargar = useCallback(async () => {
    const t = await tokenVigente();
    if (!t) return;
    try { setReportes((await apiPortal.misReportes(t)).reportes); } catch { setReportes([]); }
  }, []);
  useEffect(() => { cargar(); api.zonas().then((r) => setZonas(r.zonas)).catch(() => {}); }, [cargar]);
  const zona = zonas.find((z) => z.zonaId === perfil.zonaId);

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
      <section className="panel flex items-center gap-4 p-4">
        <div className="grid size-12 shrink-0 place-items-center rounded-full bg-acento/15 text-lg font-semibold text-acento">
          {perfil.nombre?.[0]?.toUpperCase() ?? "?"}
        </div>
        <div className="min-w-0 flex-1 text-sm">
          <div className="font-semibold">{perfil.nombre}</div>
          <div className="truncate text-xs text-tenue">{perfil.email}</div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-tenue">
            <span className="flex items-center gap-1"><Smartphone className="size-3" />Servicio {perfil.numeroServicio}</span>
            <span className="flex items-center gap-1"><MapPin className="size-3" />{zona?.nombre ?? perfil.zonaId}</span>
          </div>
        </div>
        <button onClick={cerrarSesion} className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-tenue ring-1 ring-borde hover:text-texto">
          <LogOut className="size-3.5" /> Salir
        </button>
      </section>

      <a {...enlace("/portal/reportar")} className="flex items-center justify-between rounded-xl bg-acento px-4 py-3 text-sm font-semibold text-fondo">
        Reportar un problema <ChevronRight className="size-4" />
      </a>

      <section className="panel p-4">
        <h2 className="mb-2 text-sm font-semibold">Mis reportes</h2>
        {!reportes && <Loader2 className="mx-auto size-5 animate-spin text-tenue" />}
        {reportes?.length === 0 && <p className="text-xs text-tenue">Aún no has reportado problemas.</p>}
        <ul className="divide-y divide-borde/60">
          {reportes?.map((r) => {
            const Icono = TIPO_PROBLEMA[r.tipo]?.icono ?? TIPO_PROBLEMA.OTRO.icono;
            return (
              <li key={r.incidenciaId}>
                <a {...enlace(`/portal/seguimiento/${r.incidenciaId}`)} className="flex items-center gap-3 py-2.5 hover:opacity-80">
                  <Icono className="size-4 shrink-0 text-acento" />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm">{TIPO_PROBLEMA[r.tipo]?.etiqueta} · <span className="text-tenue">{r.zona}</span></div>
                    <div className="text-[11px] text-tenue">{haceCuanto(r.creadaEn)} · ubicación por {r.ubicacionFuente === "GPS" ? "GPS" : "zona de tu cuenta"}</div>
                  </div>
                  <ChipEstado estado={r.estado} />
                </a>
              </li>
            );
          })}
        </ul>
      </section>
    </motion.div>
  );
}

function Campo({ etiqueta, required, ...props }: { etiqueta: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] text-tenue">{etiqueta}{required && <span className="text-acento"> *</span>}</span>
      <input required={required} {...props} className="w-full rounded-xl border border-borde bg-fondo px-3 py-2.5 text-sm outline-none transition focus:border-acento" />
    </label>
  );
}
