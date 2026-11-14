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

// ---------------- Incidencias (E2) ----------------
import {
  CheckCircle2, ClipboardCheck, FileText, Gauge, MessageSquareOff, PhoneOff, SearchCheck, SignalZero,
  Waves, WifiOff, Wrench, HelpCircle, Archive,
} from "lucide-react";
import type { EstadoIncidencia, TipoProblema } from "./api";

export const ESTADO_INCIDENCIA: Record<EstadoIncidencia, { etiqueta: string; color: string; icono: LucideIcon; ayuda: string }> = {
  REGISTRADA: { etiqueta: "Registrada", color: "#60a5fa", icono: FileText, ayuda: "Recibimos tu reporte" },
  EN_REVISION: { etiqueta: "En revisión", color: "#a78bfa", icono: SearchCheck, ayuda: "Un operador lo está revisando" },
  EN_ATENCION: { etiqueta: "Siendo atendida", color: "#f59e0b", icono: Wrench, ayuda: "Un equipo técnico está trabajando" },
  SOLUCIONADA: { etiqueta: "Solucionada", color: "#22c55e", icono: CheckCircle2, ayuda: "El problema fue resuelto" },
  CERRADA: { etiqueta: "Cerrada", color: "#94a3b8", icono: Archive, ayuda: "Caso cerrado" },
};
export const ORDEN_INCIDENCIA: EstadoIncidencia[] = ["REGISTRADA", "EN_REVISION", "EN_ATENCION", "SOLUCIONADA", "CERRADA"];

export const TIPO_PROBLEMA: Record<TipoProblema, { etiqueta: string; icono: LucideIcon }> = {
  SIN_INTERNET: { etiqueta: "Sin Internet", icono: WifiOff },
  INTERNET_LENTO: { etiqueta: "Internet lento", icono: Gauge },
  SIN_LLAMADAS: { etiqueta: "No puedo llamar", icono: PhoneOff },
  SIN_SMS: { etiqueta: "No llegan SMS", icono: MessageSquareOff },
  SIN_SENAL: { etiqueta: "Sin señal", icono: SignalZero },
  INTERMITENCIA: { etiqueta: "Se corta", icono: Waves },
  OTRO: { etiqueta: "Otro", icono: HelpCircle },
};

export const EVENTO: Record<string, { etiqueta: string; icono: LucideIcon }> = {
  CREADO: { etiqueta: "Reporte registrado", icono: ClipboardCheck },
  CAMBIO_ESTADO: { etiqueta: "Cambio de estado", icono: Wrench },
};
