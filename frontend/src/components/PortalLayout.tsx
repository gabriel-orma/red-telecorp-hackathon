import type { ReactNode } from "react";
import { Radio } from "lucide-react";
import { enlace } from "../lib/router";

/** Marco del portal del usuario: mobile-first, centrado y sin la densidad del centro de control. */
export function PortalLayout({ children }: { children: ReactNode }) {
  return (
    <div className="fondo-rejilla min-h-full">
      <header className="sticky top-0 z-20 border-b border-borde bg-fondo/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-xl items-center justify-between px-4">
          <a {...enlace("/portal")} className="flex items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-acento/10 ring-1 ring-acento/30">
              <Radio className="size-4 text-acento" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">Red TeleCorp</div>
              <div className="text-[10px] uppercase tracking-[0.14em] text-tenue">Atención al cliente</div>
            </div>
          </a>
          <a {...enlace("/")} className="text-[11px] text-tenue hover:text-texto">Centro de control →</a>
        </div>
      </header>
      <main className="mx-auto max-w-xl px-4 pb-16 pt-6">{children}</main>
    </div>
  );
}

/** Reportes hechos desde este navegador (solo comodidad local; la fuente de verdad es el backend). */
const CLAVE = "telecorp.misReportes";
export function misReportes(): { id: string; creado: string; tipo: string }[] {
  try { return JSON.parse(localStorage.getItem(CLAVE) ?? "[]"); } catch { return []; }
}
export function guardarReporte(id: string, tipo: string) {
  try {
    const lista = misReportes().filter((r) => r.id !== id);
    localStorage.setItem(CLAVE, JSON.stringify([{ id, tipo, creado: new Date().toISOString() }, ...lista].slice(0, 10)));
  } catch { /* almacenamiento no disponible */ }
}
