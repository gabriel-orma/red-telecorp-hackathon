import { useCallback } from "react";
import { api } from "./lib/api";
import { useRuta } from "./lib/router";
import { usePolling } from "./hooks/usePolling";
import { Encabezado } from "./components/Encabezado";
import { CentroControl } from "./pages/CentroControl";
import { PanelIncidencias } from "./pages/PanelIncidencias";
import { Portal } from "./pages/Portal";
import { Seguimiento } from "./pages/Seguimiento";

const POLLING_MS = 3000;

export default function App() {
  const ruta = useRuta();

  // Portal del usuario: layout propio, mobile-first.
  if (ruta.startsWith("/portal")) {
    const m = ruta.match(/^\/portal\/seguimiento\/([^/]+)/);
    return m ? <Seguimiento incidenciaId={decodeURIComponent(m[1])} /> : <Portal />;
  }
  return <Operador ruta={ruta} />;
}

function Operador({ ruta }: { ruta: string }) {
  const red = usePolling(
    useCallback(async () => {
      const [a, z] = await Promise.all([api.antenas(), api.zonas()]);
      return { antenas: a.antenas, zonas: z.zonas };
    }, []),
    POLLING_MS,
  );
  return (
    <div className="fondo-rejilla flex h-full flex-col">
      <Encabezado ultimaCarga={red.ultimaCarga} error={red.error} />
      {ruta === "/incidencias" ? (
        <PanelIncidencias zonas={red.datos?.zonas ?? []} />
      ) : (
        <CentroControl
          antenas={red.datos?.antenas ?? []}
          zonas={red.datos?.zonas ?? []}
          cargando={!red.datos && !red.error}
          refrescarRed={red.refrescar}
        />
      )}
    </div>
  );
}
