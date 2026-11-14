import type { ReactNode } from "react";
import { Activity, Megaphone, Radio, UserRound } from "lucide-react";
import { usePerfil } from "../lib/auth";
import { enlace, useRuta } from "../lib/router";
import { cn } from "../lib/utils";

/** Marco del portal de clientes: mobile-first, con navegación Estado · Reportar · Cuenta. */
export function PortalLayout({ children }: { children: ReactNode }) {
  const ruta = useRuta().split("?")[0];
  const perfil = usePerfil();
  const item = (destino: string, etiqueta: string, Icono: typeof Activity) => (
    <a {...enlace(destino)}
      className={cn("flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition",
        ruta === destino ? "bg-panel-2 text-texto ring-1 ring-borde" : "text-tenue hover:text-texto")}>
      <Icono className="size-3.5" /> <span>{etiqueta}</span>
    </a>
  );
  return (
    <div className="fondo-rejilla min-h-full">
      <header className="sticky top-0 z-20 border-b border-borde bg-fondo/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between gap-2 px-4">
          <a {...enlace("/portal")} className="flex shrink-0 items-center gap-2.5">
            <div className="grid size-8 place-items-center rounded-lg bg-acento/10 ring-1 ring-acento/30">
              <Radio className="size-4 text-acento" />
            </div>
            <div className="hidden leading-tight sm:block">
              <div className="text-sm font-semibold">Red TeleCorp</div>
              <div className="text-[10px] uppercase tracking-[0.14em] text-tenue">Estado del servicio</div>
            </div>
          </a>
          <nav className="flex items-center gap-1">
            {item("/portal", "Estado", Activity)}
            {item("/portal/reportar", "Reportar", Megaphone)}
            {item("/portal/cuenta", perfil ? perfil.nombre.split(" ")[0] : "Ingresar", UserRound)}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">{children}</main>
    </div>
  );
}
