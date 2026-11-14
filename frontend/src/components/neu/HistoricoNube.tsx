import { useCallback } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, Database, HelpCircle, Loader2, Timer, Siren } from "lucide-react";
import { apiHistorico, type Historico } from "../../lib/api";
import { TIPO_PROBLEMA } from "../../lib/estados";
import { usePolling } from "../../hooks/usePolling";
import { Cifra } from "./Piezas";

const EJE = { fill: "#8b8b97", fontSize: 11 };
const TOOLTIP = { contentStyle: { background: "#1c1c21", border: "none", borderRadius: 14, boxShadow: "6px 6px 16px #0a0a0c", fontSize: 12 },
                  labelStyle: { color: "#ececf1", fontWeight: 600 }, cursor: { fill: "#ffffff08" } };
const minutos = (m: number | null) => m === null ? "—" : m >= 60 ? `${(m / 60).toFixed(1)} h` : `${Math.round(m)} min`;

// La procedencia se dice tal cual: «BigQuery» (Google Cloud) o el respaldo en DynamoDB (AWS). Texto + icono, nunca solo color.
const ORIGEN = {
  BigQuery: { titulo: "BigQuery · Google Cloud", nota: "Histórico consultado en BigQuery con SQL" },
  DynamoDB: { titulo: "DynamoDB · AWS (respaldo)", nota: "BigQuery no respondió: se muestra el histórico calculado desde DynamoDB" },
} as const;

/** Histórico de incidentes cerrados: zonas con más incidentes y tipos más frecuentes, con su procedencia a la vista. */
export function HistoricoNube() {
  const reducir = useReducedMotion();
  const h = usePolling<Historico>(useCallback(() => apiHistorico.obtener(), []), 60_000);
  const origen = h.datos ? ORIGEN[h.datos.fuente] ?? { titulo: h.datos.fuente, nota: "" } : null;

  return (
    <section className="neu p-5" aria-label="Histórico de incidentes en la nube">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold">Histórico de incidentes</h2>
          <p className="text-xs text-tenue">Incidentes colectivos cerrados, agregados fuera de la base operativa para análisis de largo plazo</p>
        </div>
        {origen && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-fondo/70 px-2.5 py-1 text-[11px] font-semibold text-texto ring-1 ring-acento/60" title={origen.nota}>
            <Database className="size-3.5 text-acento" aria-hidden />{origen.titulo}
          </span>
        )}
      </div>

      {!h.datos && !h.error && <div className="grid h-40 place-items-center"><Loader2 className="size-5 animate-spin text-tenue motion-reduce:animate-none" /></div>}

      {!h.datos && h.error && (
        <div role="status" className="flex items-center gap-3 rounded-2xl bg-fondo/60 px-4 py-6 text-sm text-tenue">
          <HelpCircle className="size-5 shrink-0" aria-hidden />
          Aún no hay datos históricos: el endpoint <code className="cifra text-texto">/api/analitica/historico</code> no respondió.
        </div>
      )}

      {h.datos && h.datos.total === 0 && (
        <div className="grid h-40 place-items-center text-center text-sm text-tenue">
          <div><BarChart3 className="mx-auto mb-2 size-7 opacity-60" aria-hidden />Todavía no hay incidentes cerrados en el histórico.
            <div className="mt-1 text-[11px]">Se cargan al cerrarse cada incidente colectivo.</div></div>
        </div>
      )}

      {h.datos && h.datos.total > 0 && (
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="neu-hundido p-4">
                <Siren className="mb-1 size-4 text-acento" aria-hidden />
                <div className="text-2xl font-bold"><Cifra valor={h.datos.total} /></div>
                <div className="text-[11px] text-tenue">incidentes en el histórico</div>
              </div>
              <div className="neu-hundido p-4">
                <Timer className="mb-1 size-4 text-acento" aria-hidden />
                <div className="text-2xl font-bold">{minutos(h.datos.duracionPromedioMin)}</div>
                <div className="text-[11px] text-tenue">duración promedio</div>
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-[11px] text-tenue">Tipos de problema más frecuentes</h3>
              <ul className="space-y-2.5">
                {(() => {
                  const max = Math.max(1, ...h.datos.tipos.map((t) => t.cantidad));
                  return h.datos.tipos.slice(0, 6).map((t) => {
                    const I = TIPO_PROBLEMA[t.tipo]?.icono ?? TIPO_PROBLEMA.OTRO.icono;
                    return (
                      <li key={t.tipo}>
                        <div className="mb-1 flex items-center justify-between text-sm">
                          <span className="flex items-center gap-2"><I className="size-4 text-acento" aria-hidden />{TIPO_PROBLEMA[t.tipo]?.etiqueta ?? t.tipo}</span>
                          <b className="text-xs"><Cifra valor={t.cantidad} /></b>
                        </div>
                        <div className="neu-hundido h-2.5 overflow-hidden rounded-full">
                          <motion.div className="degradado h-full rounded-full" initial={reducir ? false : { width: 0 }}
                            animate={{ width: `${(100 * t.cantidad) / max}%` }} transition={{ duration: reducir ? 0 : 0.6, ease: [0.23, 1, 0.32, 1] }} />
                        </div>
                      </li>
                    );
                  });
                })()}
              </ul>
            </div>
          </div>

          <div>
            <h3 className="mb-2 text-[11px] text-tenue">Zonas con más incidentes</h3>
            <ResponsiveContainer width="100%" height={Math.max(180, 34 * Math.min(8, h.datos.zonasTop.length))}>
              <BarChart data={h.datos.zonasTop.slice(0, 8)} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid horizontal={false} stroke="#2a2a31" />
                <XAxis type="number" tick={EJE} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis type="category" dataKey="nombre" width={130} tick={EJE} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP} />
                <Bar dataKey="incidentes" name="Incidentes" fill="#e05ab0" radius={[0, 6, 6, 0]} barSize={12} isAnimationActive={!reducir} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}
