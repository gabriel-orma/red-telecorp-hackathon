import { useCallback } from "react";
import { motion, useReducedMotion } from "framer-motion";
import {
  AlertTriangle, CheckCircle2, CircleDashed, Cloud, CloudOff, Database, HelpCircle, Inbox, Loader2, Mail,
  MapPinned, Sparkles, Workflow, Zap, type LucideIcon,
} from "lucide-react";
import { apiNubes, type EstadoNube, type Nubes as DatosNubes, type ServicioNube } from "../lib/api";
import { usePolling } from "../hooks/usePolling";
import { cn, haceCuanto } from "../lib/utils";
import { Cifra } from "../components/neu/Piezas";

interface Servicio { clave: string; nombre: string; detalle: string; icono: LucideIcon }
interface Proveedor { id: "aws" | "azure" | "ia"; nombre: string; rol: string; servicios: Servicio[] }

const PROVEEDORES: Proveedor[] = [
  { id: "aws", nombre: "Amazon Web Services", rol: "Núcleo: ingesta, datos, automatización y API", servicios: [
    { clave: "apiGateway", nombre: "API Gateway + Lambda", detalle: "Recibe reportes y sirve el panel", icono: Zap },
    { clave: "dynamodb", nombre: "DynamoDB", detalle: "Reportes, historial inmutable y antenas", icono: Database },
    { clave: "stepFunctions", nombre: "Step Functions", detalle: "Ciclo de vida del incidente colectivo", icono: Workflow },
    { clave: "sqs", nombre: "SQS + DLQ", detalle: "Buffer anti-avalancha de reportes", icono: Inbox },
  ] },
  { id: "azure", nombre: "Microsoft Azure", rol: "Avisos por correo y contexto geoespacial", servicios: [
    { clave: "acsEmail", nombre: "Communication Services · correo", detalle: "Avisos a los afectados", icono: Mail },
    { clave: "maps", nombre: "Azure Maps", detalle: "Clima actual de la zona del incidente", icono: MapPinned },
  ] },
  { id: "ia", nombre: "IA generativa (API externa)", rol: "Análisis del incidente; no cuenta como nube adicional", servicios: [
    { clave: "gemini", nombre: "Gemini API", detalle: "Hipótesis de causa y recomendaciones; si no responde, reglas deterministas", icono: Sparkles },
  ] },
];

// El estado se comunica con icono + texto + color (nunca solo color). El texto va siempre en color de alto contraste.
type EstadoVista = EstadoNube | "SIN_DATOS" | "PARCIAL";
const ESTADOS: Record<EstadoVista, { etiqueta: string; color: string; icono: LucideIcon }> = {
  OK: { etiqueta: "Operativo", color: "#2dd4bf", icono: CheckCircle2 },
  PARCIAL: { etiqueta: "Parcial", color: "#f5a524", icono: AlertTriangle },
  ERROR: { etiqueta: "Con error", color: "#f0506e", icono: AlertTriangle },
  SIN_CONFIGURAR: { etiqueta: "Sin configurar", color: "#9a9aa6", icono: CircleDashed },
  SIN_DATOS: { etiqueta: "Sin datos", color: "#6b6b78", icono: HelpCircle },
};

type Fila = ServicioNube | undefined;

/** Operativa solo si TODOS sus servicios responden; «parcial» si algunos sí y otros no (no se oculta el que falla). */
function resumenProveedor(filas: Fila[]): EstadoVista {
  const ok = filas.filter((f) => f?.estado === "OK").length;
  if (ok === filas.length) return "OK";
  if (ok > 0) return "PARCIAL";
  if (filas.some((f) => f?.estado === "ERROR")) return "ERROR";
  if (filas.some((f) => f?.estado === "SIN_CONFIGURAR")) return "SIN_CONFIGURAR";
  return "SIN_DATOS";
}

/** Nubes conectadas: checklist en vivo de qué servicio de cada proveedor está respondiendo (para el pitch). */
export function Nubes() {
  const reducir = useReducedMotion();
  const nubes = usePolling<DatosNubes>(useCallback(() => apiNubes.obtener(), []), 15_000);

  const aws = (clave: string): { fila: Fila; derivada: boolean } => {
    const informada = nubes.datos?.aws?.[clave];
    if (informada) return { fila: informada, derivada: false };
    // API Gateway + Lambda: si /api/nubes respondió, es que ambos funcionan (la propia respuesta lo prueba).
    if (clave === "apiGateway" && nubes.datos) return { fila: { estado: "OK", ultimaLlamada: new Date(nubes.ultimaCarga ?? Date.now()).toISOString() }, derivada: true };
    return { fila: undefined, derivada: false };
  };
  const fila = (p: Proveedor["id"], clave: string): { fila: Fila; derivada: boolean } => {
    if (p === "aws") return aws(clave);
    const grupo = p === "azure" ? nubes.datos?.azure : nubes.datos?.ia;
    return { fila: (grupo as Record<string, ServicioNube | undefined> | undefined)?.[clave], derivada: false };
  };

  const estados = PROVEEDORES.map((p) => ({ p, estado: resumenProveedor(p.servicios.map((s) => fila(p.id, s.clave).fila)) }));
  // «Conectada» = al menos un servicio de ese proveedor respondió bien (la integración funciona, aunque sea parcial).
  const nubesReales = estados.filter((e) => e.p.id !== "ia");   // la API de IA no es una nube adicional
  const conectadas = nubesReales.filter((e) => e.estado === "OK" || e.estado === "PARCIAL").length;
  const cargando = !nubes.datos && !nubes.error;

  return (
    <main className="scroll-fino min-h-0 flex-1 space-y-5 overflow-y-auto p-1">
      {/* Checklist de nubes */}
      <section className="neu p-5" aria-label="Resumen de nubes conectadas">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold">Integración multinube</h2>
            <p className="text-xs text-tenue">Cada servicio se consulta en vivo; «operativo» significa que respondió bien en su última llamada.</p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold"><Cifra valor={conectadas} /><span className="text-lg font-semibold text-tenue"> de {nubesReales.length}</span></div>
            <div className="text-xs text-tenue">nubes con integración operativa</div>
          </div>
        </div>
        <ul className="mt-4 flex flex-wrap gap-2">
          {estados.map(({ p, estado }) => {
            const e = ESTADOS[estado];
            return (
              <li key={p.id} className="neu-hundido flex items-center gap-2 px-3 py-2 text-sm font-semibold">
                <e.icono className="size-4" style={{ color: e.color }} aria-hidden />
                {p.nombre}
                <span className="text-xs font-normal text-tenue">· {e.etiqueta}</span>
              </li>
            );
          })}
        </ul>
        {nubes.error && !nubes.datos && (
          <p role="status" className="mt-4 flex items-center gap-2 rounded-2xl bg-fondo/60 px-4 py-3 text-xs text-tenue">
            <CloudOff className="size-4 shrink-0" aria-hidden />
            Sin datos de las integraciones: el endpoint <code className="cifra text-texto">/api/nubes</code> no respondió. Sin ese dato no se afirma nada de las demás nubes.
          </p>
        )}
      </section>

      {cargando ? <div className="grid h-40 place-items-center"><Loader2 className="size-6 animate-spin text-tenue motion-reduce:animate-none" /></div> : (
        <div className="grid gap-5 xl:grid-cols-3">
          {estados.map(({ p, estado }, i) => {
            const e = ESTADOS[estado];
            return (
              <motion.section key={p.id} className="neu p-5" aria-label={p.nombre}
                initial={reducir ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: reducir ? 0 : i * 0.05 }}>
                <header className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h3 className="flex items-center gap-2 text-sm font-semibold"><Cloud className="size-4 text-acento" aria-hidden />{p.nombre}</h3>
                    <p className="text-xs text-tenue">{p.rol}</p>
                  </div>
                  <Insignia estado={estado} etiqueta={e.etiqueta} />
                </header>
                <ul className="space-y-2">
                  {p.servicios.map((s) => {
                    const { fila: f, derivada } = fila(p.id, s.clave);
                    return <FilaServicio key={s.clave} s={s} f={f} derivada={derivada} />;
                  })}
                </ul>
              </motion.section>
            );
          })}
        </div>
      )}
    </main>
  );
}

function Insignia({ estado, etiqueta }: { estado: EstadoVista; etiqueta: string }) {
  const e = ESTADOS[estado];
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-fondo/70 px-2.5 py-1 text-[11px] font-semibold text-texto ring-1"
      style={{ ["--tw-ring-color" as string]: e.color }}>
      <e.icono className="size-3.5" style={{ color: e.color }} aria-hidden />{etiqueta}
    </span>
  );
}

function FilaServicio({ s, f, derivada }: { s: Servicio; f: Fila; derivada: boolean }) {
  const estado: EstadoVista = f?.estado ?? "SIN_DATOS";
  const e = ESTADOS[estado];
  return (
    <li className="neu-hundido px-3 py-2.5">
      <div className="flex items-center gap-3">
        <s.icono className="size-4 shrink-0 text-acento" aria-hidden />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{s.nombre}</div>
          <div className="truncate text-[11px] text-tenue">{s.detalle}</div>
        </div>
        <Insignia estado={estado} etiqueta={e.etiqueta} />
      </div>
      <div className={cn("mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-0.5 pl-7 text-[11px] text-tenue", !f && "opacity-70")}>
        <span>última llamada <b className="cifra font-medium text-texto">{f?.ultimaLlamada ? haceCuanto(f.ultimaLlamada) : "—"}</b></span>
        {f?.contador !== undefined && <span><b className="cifra font-medium text-texto"><Cifra valor={f.contador} /></b> {f.detalle && derivada ? f.detalle : "llamadas"}</span>}
        {derivada && <span title="El backend aún no informa esta fila; se mide desde lo que el panel puede leer">medido desde el panel</span>}
      </div>
      {f?.detalle && !derivada && <div className="mt-1 truncate pl-7 text-[11px] text-tenue" title={f.detalle}>{f.detalle}</div>}
    </li>
  );
}
