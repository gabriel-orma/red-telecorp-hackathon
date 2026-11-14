import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EstadoRed } from "../lib/api";

const hora = (iso: string) =>
  new Date(iso).toLocaleTimeString("es-PE", { timeZone: "America/Lima", hour: "numeric", minute: "2-digit", hour12: true });

/** Reportes por bloque de 15 min en las últimas 24 h, contra la línea base (lo normal a esa hora). Estilo Downdetector. */
export function GraficoReportes({ serie, color = "#22d3ee" }: { serie: EstadoRed["serie"]; color?: string }) {
  const datos = serie.map((p) => ({ ...p, etiqueta: hora(p.t) }));
  const max = Math.max(5, ...serie.map((p) => Math.max(p.total, p.base)));
  return (
    <div className="h-56 w-full sm:h-64">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={datos} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="relleno" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.75} />
              <stop offset="100%" stopColor={color} stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="#1c2a45" strokeDasharray="0" />
          <XAxis dataKey="etiqueta" interval={11} tick={{ fill: "#8796b0", fontSize: 10 }} tickLine={false} axisLine={{ stroke: "#1c2a45" }} />
          <YAxis domain={[0, Math.ceil(max * 1.2)]} allowDecimals={false} tick={{ fill: "#8796b0", fontSize: 10 }} tickLine={false} axisLine={false} />
          <Tooltip
            cursor={{ stroke: "#475569", strokeDasharray: "3 3" }}
            contentStyle={{ background: "#0b1222", border: "1px solid #1c2a45", borderRadius: 10, fontSize: 12 }}
            labelStyle={{ color: "#e6edf7", fontWeight: 600 }}
            formatter={(v, n) => [n === "total" ? `${v} reportes` : `${v} (normal)`, n === "total" ? "Reportes" : "Línea base"] as [string, string]}
          />
          <Area type="monotone" dataKey="total" stroke={color} strokeWidth={2} fill="url(#relleno)" isAnimationActive animationDuration={700} />
          <Line type="monotone" dataKey="base" stroke="#e6edf7" strokeOpacity={0.8} strokeWidth={1.5} strokeDasharray="4 4" dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
