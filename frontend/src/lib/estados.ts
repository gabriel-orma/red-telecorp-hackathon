import {
  Building2,
  Factory,
  GraduationCap,
  Home,
  HeartPulse,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";
import type { EstadoAntena, TipoZona } from "./api";

// Presentación de los estados. Las reglas (umbrales) viven en el backend; aquí solo color y texto.
export const ESTADO: Record<EstadoAntena, { etiqueta: string; color: string; rango: string }> = {
  NORMAL: { etiqueta: "Normal", color: "#22c55e", rango: "60–129 GB/min" },
  SATURADA: { etiqueta: "Saturada", color: "#f59e0b", rango: "> 129 GB/min" },
  CAIDA: { etiqueta: "Caída", color: "#ef4444", rango: "< 60 GB/min" },
  INHABILITADA: { etiqueta: "Inhabilitada", color: "#94a3b8", rango: "0 GB/min" },
  SIN_DATOS: { etiqueta: "Sin datos", color: "#475569", rango: "sin lecturas" },
};

export const ORDEN_ESTADOS: EstadoAntena[] = ["NORMAL", "SATURADA", "CAIDA", "INHABILITADA"];
export const GRAVEDAD: Record<EstadoAntena, number> = { SIN_DATOS: 0, NORMAL: 1, SATURADA: 2, CAIDA: 3, INHABILITADA: 4 };
export const ES_FALLA = (e: EstadoAntena) => e === "CAIDA" || e === "INHABILITADA";

export const TIPO_ZONA: Record<TipoZona, { etiqueta: string; icono: LucideIcon }> = {
  RESIDENCIAL: { etiqueta: "Residencial", icono: Home },
  COMERCIAL: { etiqueta: "Comercial", icono: Building2 },
  INDUSTRIAL: { etiqueta: "Industrial", icono: Factory },
  EDUCATIVA: { etiqueta: "Educativa", icono: GraduationCap },
  MEDICA: { etiqueta: "Médica", icono: HeartPulse },
  SERVICIOS_CRITICOS: { etiqueta: "Servicios críticos", icono: ShieldAlert },
};
