import type { EstadoAntena, PasoColectivo } from "../../lib/api";
import type { PaletaMapa } from "../MapaRed";

/** Colores de estado del tema neumórfico: saturados para que las fallas se lean de un vistazo. */
export const COLOR_NEU: Record<EstadoAntena, string> = {
  NORMAL: "#2dd4bf",
  SATURADA: "#f5a524",
  CAIDA: "#f0506e",
  INHABILITADA: "#9a9aa6",
  SIN_DATOS: "#4a4a55",
};

export const PALETA_MAPA_NEU: PaletaMapa = {
  estados: COLOR_NEU,
  zonas: { CAIDA: "#c2566a", INHABILITADA: "#7d7d88", SATURADA: "#b9894a", OTRA: "#4b4b58" },
};

/** Los 12 pasos de la Step Function agrupados en 4 etapas legibles (estilo "Sign up → Verify → …"). */
export const ETAPAS: { etiqueta: string; pasos: PasoColectivo[] }[] = [
  { etiqueta: "Detectado", pasos: ["DETECTADO", "NOTIFICAR_EVALUACION"] },
  { etiqueta: "Verificado y priorizado", pasos: ["VERIFICAR_INFRAESTRUCTURA", "PRIORIZAR", "RESUMIR", "CONFIRMAR", "NOTIFICAR_CONFIRMADA", "ALERTAR_OPERADOR"] },
  { etiqueta: "Monitoreando", pasos: ["MONITOREAR"] },
  { etiqueta: "Restablecido", pasos: ["RESTABLECER", "NOTIFICAR_RESTABLECIDO", "CERRADO"] },
];
export const etapaDe = (paso: PasoColectivo) => ETAPAS.findIndex((e) => e.pasos.includes(paso));
