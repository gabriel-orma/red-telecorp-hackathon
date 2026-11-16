import { LogIn, X } from "lucide-react";
import { descartarAvisoSesion, useSesionCaducada } from "../lib/auth";
import { enlace } from "../lib/router";

/** Aviso visible (y anunciado a lectores de pantalla) cuando la sesión caducó: antes el panel solo dejaba de actualizarse. */
export function AvisoSesion() {
  const caducada = useSesionCaducada();
  if (!caducada) return null;
  return (
    <div role="alert" className="flex flex-wrap items-center gap-3 rounded-2xl bg-saturada/10 px-4 py-3 text-sm ring-1 ring-saturada/40">
      <LogIn className="size-4 shrink-0 text-saturada" aria-hidden="true" />
      <span className="min-w-0 flex-1">Tu sesión caducó. Las pantallas de operador no se actualizarán hasta que ingreses de nuevo.</span>
      <a {...enlace("/portal/cuenta")} className="rounded-lg bg-saturada/20 px-3 py-1.5 text-xs font-semibold text-texto ring-1 ring-saturada/50">Ingresar de nuevo</a>
      <button onClick={descartarAvisoSesion} aria-label="Cerrar aviso" className="rounded-md p-1 text-tenue hover:text-texto"><X className="size-4" aria-hidden="true" /></button>
    </div>
  );
}
