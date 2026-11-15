import { useEffect, type ReactNode } from "react";
import { Activity, Megaphone, Radio, UserRound } from "lucide-react";
import { usePerfil } from "../lib/auth";
import { enlace, useRuta } from "../lib/router";
import { cn } from "../lib/utils";

/** Marco del portal de clientes: mobile-first, con navegación Estado · Reportar · Cuenta. */
export function PortalLayout({ children }: { children: ReactNode }) {
  const ruta = useRuta().split("?")[0];
  const perfil = usePerfil();
  useEffect(() => { document.title = "Estado del servicio · Red TeleCorp"; }, []);
  const item = (destino: string, etiqueta: string, Icono: typeof Activity) => (
    <a {...enlace(destino)} aria-current={ruta === destino ? "page" : undefined} data-activo={ruta === destino}
      className={cn("boton-neu flex items-center gap-1.5 px-3 py-2 text-xs font-medium",
        ruta === destino ? "text-acento" : "text-tenue")}>
      <Icono className="size-3.5" /> <span>{etiqueta}</span>
    </a>
  );
  return (
    <div className="tema-neu min-h-full">
      <header className="sticky top-0 z-20 bg-fondo/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between gap-2 px-4">
          <a {...enlace("/portal")} aria-label="Red TeleCorp, estado del servicio" className="flex shrink-0 items-center gap-2.5">
            <div className="degradado grid size-9 place-items-center rounded-2xl text-white">
              <Radio className="size-4" />
            </div>
            <div className="hidden leading-tight sm:block">
              <div className="text-sm font-semibold">Red TeleCorp</div>
              <div className="text-[11px] text-tenue">Estado del servicio</div>
            </div>
          </a>
          <nav className="flex items-center gap-2">
            {item("/portal", "Estado", Activity)}
            {item("/portal/reportar", "Reportar", Megaphone)}
            {item("/portal/cuenta", perfil ? (perfil.nombre || perfil.email || "Mi cuenta").split(" ")[0] : "Ingresar", UserRound)}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">{children}</main>
    </div>
  );
}
