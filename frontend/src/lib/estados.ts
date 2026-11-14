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
  CREADO: { etiqueta: "Registrado", icono: ClipboardCheck },
  CAMBIO_ESTADO: { etiqueta: "Cambio de estado", icono: Wrench },
  AGRUPADO: { etiqueta: "Agrupado en un incidente colectivo", icono: ClipboardCheck },
  PRIORIDAD_ASIGNADA: { etiqueta: "Prioridad asignada", icono: Wrench },
  COMENTARIO: { etiqueta: "Nota", icono: FileText },
};

// ---------------- Incidentes colectivos (E3) ----------------
import {
  AlertTriangle, BellRing, Brain, CheckCheck, Flag, Gauge as GaugeIcon, Megaphone, RadioTower, RefreshCw, Siren, Sparkles,
} from "lucide-react";
import type { EstadoColectivo, PasoColectivo, Prioridad } from "./api";

export const ESTADO_COLECTIVO: Record<EstadoColectivo, { etiqueta: string; color: string }> = {
  EN_EVALUACION: { etiqueta: "En evaluación", color: "#a78bfa" },
  INCIDENCIA_CONFIRMADA: { etiqueta: "Incidencia confirmada", color: "#ef4444" },
  SERVICIO_RESTABLECIDO: { etiqueta: "Servicio restablecido", color: "#22c55e" },
  CERRADO: { etiqueta: "Cerrado", color: "#94a3b8" },
};

export const PRIORIDAD: Record<Prioridad, { etiqueta: string; color: string }> = {
  BAJA: { etiqueta: "Baja", color: "#60a5fa" },
  MEDIA: { etiqueta: "Media", color: "#f59e0b" },
  ALTA: { etiqueta: "Alta", color: "#f97316" },
  CRITICA: { etiqueta: "Crítica", color: "#ef4444" },
};

/** Pasos de la Step Function `incidente-colectivo`, en orden (para el diagrama). */
export const PASOS_FLUJO: { paso: PasoColectivo; etiqueta: string; detalle: string; icono: LucideIcon; tipo?: "map" | "choice" | "loop" }[] = [
  { paso: "DETECTADO", etiqueta: "Detección", detalle: "≥10 usuarios / zona / 24 h o antena caída", icono: AlertTriangle },
  { paso: "NOTIFICAR_EVALUACION", etiqueta: "Aviso: en evaluación", detalle: "Map → un aviso por afectado", icono: Megaphone, tipo: "map" },
  { paso: "VERIFICAR_INFRAESTRUCTURA", etiqueta: "Verificar infraestructura", detalle: "Correlación con antenas de la zona", icono: RadioTower },
  { paso: "PRIORIZAR", etiqueta: "Priorizar", detalle: "Afectados × criticidad de zona", icono: GaugeIcon },
  { paso: "RESUMIR", etiqueta: "Resumen para el operador", detalle: "IA de la 2.ª nube (E4)", icono: Brain },
  { paso: "CONFIRMAR", etiqueta: "Confirmar incidencia", detalle: "Incidencias → siendo atendidas", icono: Flag },
  { paso: "NOTIFICAR_CONFIRMADA", etiqueta: "Aviso: incidencia en la zona", detalle: "Map → un aviso por afectado", icono: BellRing, tipo: "map" },
  { paso: "ALERTAR_OPERADOR", etiqueta: "¿Crítico? Alerta al NOC", detalle: "Choice + SNS directo", icono: Siren, tipo: "choice" },
  { paso: "MONITOREAR", etiqueta: "Monitoreo", detalle: "Wait + re-verificación periódica", icono: RefreshCw, tipo: "loop" },
  { paso: "RESTABLECER", etiqueta: "Servicio restablecido", detalle: "Automático (antenas OK) o por operador", icono: Sparkles },
  { paso: "NOTIFICAR_RESTABLECIDO", etiqueta: "Aviso: restablecido", detalle: "Map → un aviso por afectado", icono: Megaphone, tipo: "map" },
  { paso: "CERRADO", etiqueta: "Cierre", detalle: "Incidencias solucionadas + duración", icono: CheckCheck },
];
