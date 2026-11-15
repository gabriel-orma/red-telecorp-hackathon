import { motion, useReducedMotion } from "framer-motion";
import { Brain, CloudRain, CloudSun, ListChecks, Loader2, Sparkles, Wind } from "lucide-react";
import type { AnalisisIA, Colectivo, PasoColectivo, ProbabilidadCausa } from "../../lib/api";
import { cn, haceCuanto } from "../../lib/utils";

// Pasos del flujo que ocurren ANTES de que se genere el análisis (paso RESUMIR): mientras tanto se muestra «analizando».
const PASOS_PREVIOS: PasoColectivo[] = ["DETECTADO", "NOTIFICAR_EVALUACION", "VERIFICAR_INFRAESTRUCTURA", "PRIORIZAR", "RESUMIR"];

// Probabilidad categórica: color + texto + número de segmentos (nunca solo color). Tonos neutros, sin semántica de «falla».
const PROBABILIDAD: Record<ProbabilidadCausa, { etiqueta: string; color: string; nivel: number }> = {
  ALTA: { etiqueta: "Probabilidad alta", color: "#e05ab0", nivel: 3 },
  MEDIA: { etiqueta: "Probabilidad media", color: "#a78bfa", nivel: 2 },
  BAJA: { etiqueta: "Probabilidad baja", color: "#9a9aa6", nivel: 1 },
};

/** Solo es «IA» lo que un modelo generó. El respaldo determinista (`REGLAS`) nunca se presenta como IA. */
export const esAnalisisDeIA = (a: AnalisisIA) => a.fuente === "IA" && a.proveedor !== "reglas";

const NOMBRE_PROVEEDOR: Record<string, string> = { gemini: "Gemini" };
// Por qué el análisis lo hizo el respaldo y no un modelo (lenguaje llano; el código técnico queda en el `title`).
const MOTIVO: Record<string, string> = {
  NO_CONFIGURADA: "la IA no está configurada en este entorno", LIMITE: "se alcanzó el cupo gratuito de la IA", DISYUNTOR: "la IA falló varias veces seguidas y se pausó",
  HTTP_429: "la IA rechazó la petición por exceso de uso", SALIDA_INVALIDA: "la respuesta de la IA no cumplió el formato esperado", RESPUESTA_INVALIDA: "la respuesta de la IA no cumplió el formato esperado",
  RED: "no hubo conexión con la IA",
};
const motivoLegible = (m?: string) => (m ? MOTIVO[m] ?? (m.startsWith("HTTP_") ? "la IA devolvió un error" : "la IA no respondió") : "la IA no respondió");
// Variante oscura del degradado del tema: texto blanco con contraste AA (el original da 3,4:1 en el extremo rosa).
export const DEGRADADO_TEXTO = { backgroundImage: "linear-gradient(120deg, #5b3fd9, #a1307a)" };

/** Tarjeta «Análisis de IA» del detalle de un incidente colectivo (resumen, hipótesis de causa, recomendaciones y clima). */
export function TarjetaIA({ colectivo }: { colectivo: Colectivo }) {
  const reducir = useReducedMotion();
  const a = colectivo.analisisIA ?? null;
  // Incidentes anteriores a E8 solo tienen el texto `resumenIA`, que generan las reglas: se muestra como tal.
  const heredado: AnalisisIA | null = !a && colectivo.resumenIA
    ? { fuente: "REGLAS", proveedor: "reglas", modelo: null, generadoEn: colectivo.actualizadoEn, resumen: colectivo.resumenIA,
        hipotesisCausa: [], recomendaciones: [], confianza: 0, clima: null }
    : null;
  const analisis = a ?? heredado;
  const analizando = !analisis && colectivo.estado === "EN_EVALUACION" && PASOS_PREVIOS.includes(colectivo.pasoActual);

  return (
    <motion.section aria-label="Análisis de IA del incidente" className="panel p-4"
      initial={reducir ? false : { opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <header className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <span className="neu-hundido grid size-8 place-items-center"><Brain className="size-4 text-acento" aria-hidden /></span>
          Análisis del incidente
        </h3>
        {analisis && <Procedencia a={analisis} />}
      </header>

      {analizando && (
        <div role="status" className="mt-3 flex items-center gap-3 rounded-2xl bg-fondo/60 px-4 py-4 text-sm text-tenue">
          <Loader2 className="size-4 shrink-0 animate-spin text-acento motion-reduce:animate-none" aria-hidden />
          Analizando el incidente: el análisis se genera al verificar la infraestructura de la zona.
        </div>
      )}

      {!analisis && !analizando && (
        <p className="mt-3 rounded-2xl bg-fondo/60 px-4 py-4 text-sm text-tenue">
          Sin análisis disponible para este incidente.
        </p>
      )}

      {analisis && <Cuerpo a={analisis} />}
    </motion.section>
  );
}

/** Insignia honesta de procedencia: «IA · Gemini» solo si lo generó un modelo; si no, «Reglas (sin IA)». */
function Procedencia({ a }: { a: AnalisisIA }) {
  const ia = esAnalisisDeIA(a);
  const proveedor = NOMBRE_PROVEEDOR[a.proveedor] ?? a.proveedor;
  return (
    <div className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-[11px] text-tenue">
      <span
        style={ia ? DEGRADADO_TEXTO : undefined}
        className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold",
          ia ? "text-white" : "bg-inhabilitada/20 text-texto ring-1 ring-inhabilitada/40")}
        title={ia ? `Generado por un modelo de lenguaje (${a.modelo ?? proveedor})`
          : "Respaldo determinista: el modelo no respondió, no está configurado o es un incidente anterior. Las reglas del reto nunca dependen de la IA."}>
        {ia ? <Sparkles className="size-3.5" aria-hidden /> : <ListChecks className="size-3.5" aria-hidden />}
        {ia ? `IA · ${proveedor}` : "Reglas (sin IA)"}
      </span>
      {ia && Number.isFinite(a.confianza) && (
        <span title="Confianza que declara el modelo; no es una probabilidad calibrada">
          confianza <b className="cifra text-texto">{Math.round(a.confianza * 100)}%</b>
        </span>
      )}
      <span className="cifra" title={new Date(a.generadoEn).toLocaleString("es-PE", { timeZone: "America/Lima" })}>
        {haceCuanto(a.generadoEn)}
      </span>
      {!ia && <span className="basis-full text-right" title={a.motivoFallback}>Motivo: {motivoLegible(a.motivoFallback)}</span>}
      {a.basadoEn && (
        <span className="basis-full text-right">
          basado en <b className="cifra text-texto">{a.basadoEn.afectados}</b> afectados y <b className="cifra text-texto">{a.basadoEn.antenasEnFalla}</b> antenas en falla
        </span>
      )}
    </div>
  );
}

function Cuerpo({ a }: { a: AnalisisIA }) {
  const ia = esAnalisisDeIA(a);
  return (
    <div className="mt-3 space-y-3">
      <p className="rounded-2xl bg-fondo/60 p-3 text-sm leading-relaxed">{a.resumen}</p>

      {a.clima && <Clima clima={a.clima} />}

      {a.hipotesisCausa.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-[11px] text-tenue">Hipótesis de causa</h4>
          <ul className="space-y-2">
            {a.hipotesisCausa.map((h, i) => {
              const p = PROBABILIDAD[h.probabilidad] ?? PROBABILIDAD.BAJA;
              return (
                <li key={`${h.causa}-${i}`} className="neu-hundido p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{h.causa}</span>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-fondo/70 px-2 py-0.5 text-[11px] font-semibold text-texto ring-1"
                      style={{ ["--tw-ring-color" as string]: p.color }}>
                      <span className="flex gap-0.5" aria-hidden>
                        {[1, 2, 3].map((n) => (
                          <span key={n} className="h-2.5 w-1 rounded-sm" style={{ background: n <= p.nivel ? p.color : `${p.color}40` }} />
                        ))}
                      </span>
                      {p.etiqueta}
                    </span>
                  </div>
                  {h.evidencia && <p className="mt-1 text-xs text-tenue"><span className="text-texto/80">Evidencia:</span> {h.evidencia}</p>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {a.recomendaciones.length > 0 && (
        <div>
          <h4 className="mb-1.5 text-[11px] text-tenue">Acciones recomendadas</h4>
          <ol className="space-y-1.5">
            {a.recomendaciones.map((r, i) => (
              <li key={i} className="flex items-start gap-2.5 text-sm">
                <span style={DEGRADADO_TEXTO} className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold text-white" aria-hidden>{i + 1}</span>
                <span>{r}</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      <p className="text-[10px] leading-snug text-tenue">
        {ia
          ? <>Análisis generado con {a.modelo ?? "un modelo de lenguaje"} a partir de datos del incidente, sin datos personales. La detección, los umbrales y la prioridad son reglas deterministas.</>
          : <>Análisis por reglas deterministas (sin modelo de IA). La detección, los umbrales y la prioridad son siempre reglas deterministas.</>}
      </p>
    </div>
  );
}

function Clima({ clima }: { clima: NonNullable<AnalisisIA["clima"]> }) {
  const Icono = clima.precipitacion ? CloudRain : CloudSun;
  const temperatura = Number.isFinite(clima.temperaturaC) ? clima.temperaturaC.toLocaleString("es-PE", { maximumFractionDigits: 1 }) : "—";
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-2xl bg-fondo/60 px-3 py-2 text-xs"
      title="Clima de la zona consultado a Azure Maps (Microsoft Azure) al generar el análisis">
      <span className="inline-flex items-center gap-1.5 font-semibold text-texto">
        <Icono className="size-4 text-acento" aria-hidden /> {clima.frase}
      </span>
      <span className="cifra text-texto">{temperatura} °C</span>
      <span className="inline-flex items-center gap-1 text-tenue"><Wind className="size-3.5" aria-hidden /> {Math.round(clima.vientoKmH)} km/h</span>
      {clima.precipitacion && <span className="rounded-full bg-saturada/15 px-2 py-0.5 text-[10px] font-semibold text-saturada">Con precipitación</span>}
      <span className="ml-auto text-[10px] text-tenue">Azure Maps</span>
    </div>
  );
}
