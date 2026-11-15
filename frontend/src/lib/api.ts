// Cliente del API (mismo origen: /api). Los tipos siguen contracts/.
import { tokenVigente } from "./auth";

export type EstadoAntena = "NORMAL" | "SATURADA" | "CAIDA" | "INHABILITADA" | "SIN_DATOS";
export type TipoZona = "RESIDENCIAL" | "COMERCIAL" | "INDUSTRIAL" | "EDUCATIVA" | "MEDICA" | "SERVICIOS_CRITICOS";

export interface Antena {
  antenaId: string;
  zonaId: string;
  lat: number;
  lng: number;
  estado: EstadoAntena;
  gbPorMinuto: number | null;
  actualizadoEn: string | null;
  estadoDesde: string | null;
  estructural?: { desde: string; fallas: number; ventanaDias: number } | null;
}

export interface Zona {
  zonaId: string;
  nombre: string;
  tipo: TipoZona;
  centro: { lat: number; lng: number };
  radioM: number;
  clientesEstimados: number;
  criticidad: number;
  estado: EstadoAntena;
  conteo: Partial<Record<EstadoAntena, number>>;
  traficoGbPorMinuto: number;
  antenas: { antenaId: string; lat: number; lng: number }[];
}

export interface EstadoSimulador {
  activo: boolean;
  fallas: Record<string, number>;
  probSaturacion: number;
  muestrasPorMinuto: number;
}

export interface Metrica {
  medidoEn: string;
  gbPorMinuto: number;
  estado: EstadoAntena;
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  // Con sesión, el ID token acompaña a toda llamada: las rutas de operador lo exigen y las públicas lo ignoran.
  const token = await tokenVigente();
  const r = await fetch(`/api${ruta}`, {
    ...init,
    headers: { "content-type": "application/json", ...(token ? { authorization: token } : {}), ...(init?.headers ?? {}) },
  });
  const datos = await r.json().catch(() => ({}));
  if (r.status === 401) throw new Error("Inicia sesión para continuar (las pantallas de operador requieren una cuenta con rol de operador).");
  if (!r.ok) throw new Error(datos.error ?? `Error ${r.status} en ${ruta}`);
  return datos as T;
}

export const api = {
  antenas: () => pedir<{ antenas: Antena[]; generadoEn: string }>("/antenas"),
  zonas: () => pedir<{ zonas: Zona[]; generadoEn: string }>("/zonas"),
  metricas: (antenaId: string, minutos = 30) =>
    pedir<{ metricas: Metrica[] }>(`/antenas/${antenaId}/metricas?minutos=${minutos}`),
  simulador: () => pedir<EstadoSimulador>("/simulador"),
  actualizarSimulador: (cambios: { activo?: boolean; fallas?: Record<string, number | null>; limpiarFallas?: boolean }) =>
    pedir<EstadoSimulador>("/simulador", { method: "PUT", body: JSON.stringify(cambios) }),
};

// ---------------- Incidencias (E2) ----------------
export type EstadoIncidencia = "REGISTRADA" | "EN_REVISION" | "EN_ATENCION" | "SOLUCIONADA" | "CERRADA";
export type TipoProblema = "SIN_INTERNET" | "INTERNET_LENTO" | "SIN_LLAMADAS" | "SIN_SMS" | "SIN_SENAL" | "INTERMITENCIA" | "OTRO";

export interface Reporte {
  usuarioId: string;
  nombre?: string;
  numeroServicio: string;
  email?: string;
  telefonoContacto?: string;
  zonaId: string;
  ubicacion?: { lat: number; lng: number; referencia?: string };
  fechaHoraIncidente: string;
  tipo: TipoProblema;
  descripcion: string;
  avisarPorEmail?: boolean;
}

export interface Incidencia {
  incidenciaId: string;
  estado: EstadoIncidencia;
  creadaEn: string;
  actualizadaEn: string;
  zonaId: string;
  tipo: TipoProblema;
  usuarioId: string;
  reporte: Reporte;
  incidenteColectivoId?: string | null;
  transicionesPermitidas: EstadoIncidencia[];
}

export interface EventoHistorial {
  entidadId: string;
  ocurridoEn: string;
  tipoEvento: string;
  actor: string;
  detalle: string;
  estadoAnterior: string | null;
  estadoNuevo: string | null;
  /** Canal de un aviso (`NOTIFICACION_ENVIADA`), si el backend lo informa. */
  canal?: CanalAviso;
}

export type CanalAviso = "AZURE_EMAIL" | "SNS_EMAIL" | "APP";

export interface DetalleIncidencia {
  colectivo: {
    incidenteColectivoId: string; estado: EstadoColectivo; pasoActual: PasoColectivo; prioridad: Prioridad;
    detectadoEn: string; resueltoEn: string | null; afectados: number; antenasEnFalla: number; resumenIA?: string;
  } | null;
  incidencia: Incidencia;
  historial: EventoHistorial[];
  zona: {
    zonaId: string; nombre: string; tipo: TipoZona; estadoRed: EstadoAntena;
    antenasConFalla: number; reportesActivos24h: number; usuariosAfectados24h: number;
  };
}

export interface ZonaUbicada { zonaId: string; nombre: string; tipo: TipoZona; distanciaM: number }

export const apiIncidencias = {
  reportar: (r: Reporte) =>
    pedir<{ incidenciaId: string; estado: EstadoIncidencia; duplicado: boolean; mensaje?: string }>("/reportes", {
      method: "POST", body: JSON.stringify(r),
    }),
  listar: (filtros: { zonaId?: string; estado?: string; horas?: number } = {}) => {
    const q = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return pedir<{ incidencias: Incidencia[]; total: number }>(`/incidencias?${q}`);
  },
  obtener: (id: string) => pedir<DetalleIncidencia>(`/incidencias/${id}`),
  cambiarEstado: (id: string, estado: EstadoIncidencia, comentario = "") =>
    pedir<{ incidencia: Incidencia }>(`/incidencias/${id}/estado`, {
      method: "PATCH", body: JSON.stringify({ estado, comentario }),
    }),
  ubicar: (lat: number, lng: number) => pedir<ZonaUbicada>(`/zonas/ubicar?lat=${lat}&lng=${lng}`),
};

// Vista de OPERADOR (JWT + grupo `operadores`): con el detalle del reporte. `apiIncidencias.listar/obtener` es la vista
// pública (solo tipo, zona, estado y fechas: sin nombre, GPS exacto ni descripción).
export const apiOperador = {
  listar: (filtros: { zonaId?: string; estado?: string; horas?: number } = {}) => {
    const q = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v !== undefined && v !== "").map(([k, v]) => [k, String(v)]));
    return pedir<{ incidencias: Incidencia[]; total: number }>(`/operador/incidencias?${q}`);
  },
  obtener: (id: string) => pedir<DetalleIncidencia>(`/operador/incidencias/${id}`),
};

// ---------------- Incidentes colectivos (E3) ----------------
export type EstadoColectivo = "EN_EVALUACION" | "INCIDENCIA_CONFIRMADA" | "SERVICIO_RESTABLECIDO" | "CERRADO" | "REQUIERE_ATENCION";
export type Prioridad = "BAJA" | "MEDIA" | "ALTA" | "CRITICA";
export type PasoColectivo =
  | "DETECTADO" | "NOTIFICAR_EVALUACION" | "VERIFICAR_INFRAESTRUCTURA" | "PRIORIZAR" | "RESUMIR" | "CONFIRMAR"
  | "NOTIFICAR_CONFIRMADA" | "NOTIFICAR_SIN_FALLA" | "ALERTAR_OPERADOR" | "MONITOREAR" | "RESTABLECER" | "NOTIFICAR_RESTABLECIDO" | "ATENCION_MANUAL" | "CERRADO";

export interface Colectivo {
  incidenteColectivoId: string;
  zonaId: string;
  zona: { nombre: string; tipo: TipoZona; centro: { lat: number; lng: number }; radioM: number; clientesEstimados: number };
  origen: "REPORTES_USUARIOS" | "METRICAS_ANTENA" | "AMBOS";
  origenDetalle: string;
  estado: EstadoColectivo;
  pasoActual: PasoColectivo;
  detectadoEn: string;
  actualizadoEn: string;
  resueltoEn: string | null;
  afectados: number;
  incidencias: string[];
  antenasEnFalla: { antenaId: string; estado: string; desde?: string }[];
  prioridad: Prioridad;
  puntajePrioridad: number;
  resumenIA?: string;
  /** Análisis estructurado (E8). Ausente en incidentes anteriores o mientras el paso RESUMIR no corrió. */
  analisisIA?: AnalisisIA | null;
  notificacionesEnviadas: number;
  restablecimientoSolicitado: boolean;
  primerReporteEn: string | null;
  primeraFallaEn: string | null;
  ejecucionArn?: string;
  duracionMinutos?: number;
  deteccionAnticipadaMin?: number | null;
}

export interface DetalleColectivo {
  colectivo: Colectivo;
  historial: EventoHistorial[];
  incidencias: { incidenciaId: string; estado: EstadoIncidencia; tipo: TipoProblema; creadaEn: string; descripcion: string }[];
}

export const apiColectivos = {
  listar: (todos = false) => pedir<{ colectivos: Colectivo[] }>(`/colectivos${todos ? "?todos=1" : ""}`),
  obtener: (id: string) => pedir<DetalleColectivo>(`/colectivos/${id}`),
  restablecer: (id: string) => pedir<{ mensaje: string }>(`/colectivos/${id}/restablecer`, { method: "POST" }),
};

// ---------------- Portal público y cuenta (E3.5) ----------------
export type NivelRed = "SIN_PROBLEMAS" | "POSIBLES_PROBLEMAS" | "PROBLEMAS";
export interface EstadoRed {
  generadoEn: string;
  alcance: string;
  nivel: NivelRed;
  mensaje: string;
  serie: { t: string; total: number; base: number }[];
  totales: { ultimas24h: number; ultimaHora: number; baseHora: number };
  tipos: { tipo: TipoProblema; total: number; pct: number }[];
  zonas: { zonaId: string; nombre: string; tipo: TipoZona; centro: { lat: number; lng: number }; radioM: number;
           total24h: number; ultimaHora: number; baseHora: number; nivel: NivelRed }[];
  colectivos: { incidenteColectivoId: string; zonaId: string; nombre: string; estado: EstadoColectivo; prioridad: Prioridad;
                afectados: number; detectadoEn: string; antenasEnFalla: number }[];
}

export interface MiReporte {
  incidenciaId: string; estado: EstadoIncidencia; creadaEn: string; zonaId: string; zona: string; tipo: TipoProblema;
  descripcion: string; ubicacionFuente: "GPS" | "CUENTA"; incidenteColectivoId?: string | null;
}

async function conToken<T>(ruta: string, token: string, init?: RequestInit): Promise<T> {
  return pedir<T>(ruta, { ...init, headers: { authorization: token, ...(init?.headers ?? {}) } });
}

export const apiPortal = {
  estado: (zonaId?: string) => pedir<EstadoRed>(`/estado${zonaId ? `?zonaId=${zonaId}` : ""}`),
  reportar: (token: string, cuerpo: { tipo: TipoProblema; descripcion: string; ubicacion?: { lat: number; lng: number } }) =>
    conToken<{ incidenciaId: string; duplicado: boolean; zonaId?: string; ubicacionFuente?: "GPS" | "CUENTA"; mensaje?: string }>(
      "/reportes", token, { method: "POST", body: JSON.stringify(cuerpo) }),
  misReportes: (token: string) => conToken<{ reportes: MiReporte[] }>("/mis-reportes", token),
};

// ---------------- Escenarios de demo (E5) ----------------
export type TipoEscenario = "TORMENTA" | "CORTE_ENERGIA" | "ACELERADA";
export interface EstadoEscenario {
  activo: boolean; tipo?: TipoEscenario; zonaId?: string; oleada?: number; total?: number;
  inicio?: string; fin?: string | null; reportes?: number; antenas?: number; error?: string | null;
  narrativa?: string | null; acelerada?: boolean;
}
export const apiEscenarios = {
  estado: () => pedir<EstadoEscenario>("/escenarios"),
  lanzar: (tipo: TipoEscenario, zonaId: string) => pedir<{ ejecucionArn: string }>("/escenarios", { method: "POST", body: JSON.stringify({ tipo, zonaId }) }),
  reiniciar: () => pedir<{ colectivosRestablecidos: number }>("/escenarios/reiniciar", { method: "POST" }),
};

// ---------------- Analítica operativa (E6) ----------------
export interface Analitica {
  dias: number; generadoEn: string;
  kpis: { incidentes: number; abiertos: number; duracionPromedioMin: number | null; afectadosTotales: number;
          deteccionAnticipadaPromedioMin: number | null; detectadosPrimeroPorLaRed: number; reportes: number };
  zonas: { zonaId: string; nombre: string; tipo: TipoZona; incidentes: number; reportes: number; afectados: number }[];
  antenas: { antenaId: string; zonaId: string; zona: string; fallas: number; estructural: boolean }[];
  tipos: { tipo: TipoProblema; total: number; pct: number }[];
  incidentes: { incidenteColectivoId: string; zonaId: string; nombre: string; detectadoEn: string; estado: EstadoColectivo;
                abierto: boolean; duracionMin: number | null; afectados: number; prioridad: Prioridad; puntaje: number;
                origen: string; deteccionAnticipadaMin: number | null }[];
  recurrencia: { umbralFallas: number; ventanaDias: number; ultimaEjecucion: string | null; estructurales: number };
}
export const apiAnalitica = {
  obtener: (dias: number) => pedir<Analitica>(`/analitica?dias=${dias}`),
  recurrencia: () => pedir<{ ejecucionArn: string }>("/recurrencia", { method: "POST" }),
};

// ---------------- Línea de tiempo (editor de video) ----------------
export interface DatosLineaTiempo {
  desde: string; hasta: string; horas: number; generadoEn: string;
  reportes: { id: string; t: string; zonaId: string; tipo: TipoProblema; lat?: number; lng?: number }[];
  antenas: { antenaId: string; zonaId: string; inicial: EstadoAntena; cambios: { t: string; estado: EstadoAntena }[] }[];
  colectivos: {
    id: string; zonaId: string; zonaNombre: string; origen: string; inicio: string; fin: string | null;
    prioridad: Prioridad; afectados: number;
    estados: { t: string; estado: EstadoColectivo }[]; prioridades: { t: string; prioridad: Prioridad }[];
  }[];
}
export const apiLineaTiempo = {
  obtener: (horas: number) => pedir<DatosLineaTiempo>(`/linea-tiempo?horas=${horas}`),
};

// ---------------- Análisis de IA, nubes e histórico (E8) ----------------
export type ProbabilidadCausa = "ALTA" | "MEDIA" | "BAJA";
export interface AnalisisIA {
  /** "IA" solo si un modelo respondió; "REGLAS" es el respaldo determinista (nunca se presenta como IA). */
  fuente: "IA" | "REGLAS";
  proveedor: "gemini" | "reglas";
  modelo: string | null;
  generadoEn: string;
  resumen: string;
  hipotesisCausa: { causa: string; probabilidad: ProbabilidadCausa; evidencia: string }[];
  recomendaciones: string[];
  confianza: number;
  /** Solo en el respaldo `REGLAS`: por qué no respondió la IA (NO_CONFIGURADA, LIMITE, DISYUNTOR, HTTP_429…). */
  motivoFallback?: string;
  /** Datos con los que se generó (se regenera si cambian los afectados o las antenas en falla). */
  basadoEn?: { afectados: number; antenasEnFalla: number };
  clima: { fuente: "AzureMaps"; frase: string; temperaturaC: number; precipitacion: boolean; vientoKmH: number } | null;
}

export type EstadoNube = "OK" | "ERROR" | "SIN_CONFIGURAR" | "SIN_DATOS";
export interface ServicioNube { estado: EstadoNube; ultimaLlamada?: string | null; contador?: number; detalle?: string }
export interface Nubes {
  aws?: Record<string, ServicioNube>;
  azure?: { acsEmail?: ServicioNube; maps?: ServicioNube };
  /** Inferencia de IA por API externa (Gemini): NO cuenta como nube adicional. */
  ia?: { gemini?: ServicioNube };
}
export const apiNubes = { obtener: () => pedir<Nubes>("/nubes") };

