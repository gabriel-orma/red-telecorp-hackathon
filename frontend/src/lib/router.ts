import { useEffect, useState } from "react";

// Router mínimo con la History API (la Lambda `web` devuelve index.html para cualquier ruta sin extensión).
export function navegar(ruta: string) {
  if (ruta === window.location.pathname) return;
  window.history.pushState({}, "", ruta);
  window.dispatchEvent(new PopStateEvent("popstate"));
  window.scrollTo(0, 0);
}

export function useRuta(): string {
  const [ruta, setRuta] = useState(window.location.pathname);
  useEffect(() => {
    const cambio = () => setRuta(window.location.pathname);
    window.addEventListener("popstate", cambio);
    return () => window.removeEventListener("popstate", cambio);
  }, []);
  return ruta;
}

/** Enlace que navega sin recargar. */
export function enlace(ruta: string) {
  return {
    href: ruta,
    onClick: (e: React.MouseEvent) => {
      if (e.metaKey || e.ctrlKey || e.button !== 0) return;
      e.preventDefault();
      navegar(ruta);
    },
  };
}
