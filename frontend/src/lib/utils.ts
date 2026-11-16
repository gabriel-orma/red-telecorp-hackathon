import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...clases: ClassValue[]) {
  return twMerge(clsx(clases));
}

const fmtNumero = new Intl.NumberFormat("es-PE");
export const numero = (n: number) => fmtNumero.format(n);

/** "hace 12 s", "hace 3 min", "hace 2 h" */
export function haceCuanto(iso: string | null | undefined, ahora = Date.now()): string {
  if (!iso) return "—";
  const s = Math.max(0, Math.round((ahora - new Date(iso).getTime()) / 1000));
  if (s < 60) return `hace ${s} s`;
  const m = Math.round(s / 60);
  if (m < 60) return `hace ${m} min`;
  return `hace ${Math.round(m / 60)} h`;
}

/** Privacidad: la ubicación del usuario se redondea a 3 decimales (≈ 110 m). Basta para ubicar su zona (radio ≥ 1 km) y evita enviar su posición exacta. */
export const aproximarCoordenada = (n: number) => Math.round(n * 1000) / 1000;

export const horaLima = (d = new Date()) =>
  d.toLocaleTimeString("es-PE", { timeZone: "America/Lima", hour12: false });
