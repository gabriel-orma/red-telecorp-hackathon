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
