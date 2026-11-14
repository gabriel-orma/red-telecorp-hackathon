// Cliente del API (mismo origen: /api). Los tipos siguen contracts/.

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
  const r = await fetch(`/api${ruta}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
  });
  const datos = await r.json().catch(() => ({}));
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
}

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

// ---------------- Incidentes colectivos (E3) ----------------
export type EstadoColectivo = "EN_EVALUACION" | "INCIDENCIA_CONFIRMADA" | "SERVICIO_RESTABLECIDO" | "CERRADO";
export type Prioridad = "BAJA" | "MEDIA" | "ALTA" | "CRITICA";
export type PasoColectivo =
  | "DETECTADO" | "NOTIFICAR_EVALUACION" | "VERIFICAR_INFRAESTRUCTURA" | "PRIORIZAR" | "RESUMIR" | "CONFIRMAR"
  | "NOTIFICAR_CONFIRMADA" | "ALERTAR_OPERADOR" | "MONITOREAR" | "RESTABLECER" | "NOTIFICAR_RESTABLECIDO" | "CERRADO";

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
  notificacionesEnviadas: number;
  restablecimientoSolicitado: boolean;
  primerReporteEn: string | null;
  primeraFallaEn: string | null;
  ejecucionArn?: string;
  duracionMinutos?: number;
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
