import { useCallback } from "react";
import { api, apiColectivos } from "./lib/api";
import { useRuta } from "./lib/router";
import { usePolling } from "./hooks/usePolling";
import { Encabezado } from "./components/Encabezado";
import { CentroControl } from "./pages/CentroControl";
import { PanelIncidencias } from "./pages/PanelIncidencias";
import { EstadoPublico } from "./pages/EstadoPublico";
import { Cuenta } from "./pages/Cuenta";
import { Reportar } from "./pages/Reportar";
import { Seguimiento } from "./pages/Seguimiento";
import { Colectivos } from "./pages/Colectivos";
import { AlertaColectivo } from "./components/AlertaColectivo";

const POLLING_MS = 3000;

export default function App() {
  const ruta = useRuta().split("?")[0];

  // Portal del usuario: layout propio, mobile-first.
  if (ruta.startsWith("/portal")) {
    const m = ruta.match(/^\/portal\/seguimiento\/([^/]+)/);
    if (m) return <Seguimiento incidenciaId={decodeURIComponent(m[1])} />;
    if (ruta === "/portal/cuenta") return <Cuenta />;
    if (ruta === "/portal/reportar") return <Reportar />;
    return <EstadoPublico />;
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
  const colectivos = usePolling(useCallback(() => apiColectivos.listar().then((r) => r.colectivos), []), POLLING_MS);
  return (
    <div className="fondo-rejilla flex h-full flex-col">
      <Encabezado ultimaCarga={red.ultimaCarga} error={red.error} colectivosActivos={colectivos.datos?.filter((c) => c.estado !== "SERVICIO_RESTABLECIDO").length ?? 0} />
      <AlertaColectivo colectivos={colectivos.datos} />
      {ruta === "/incidencias" ? (
        <PanelIncidencias zonas={red.datos?.zonas ?? []} />
      ) : ruta === "/colectivos" ? (
        <Colectivos abiertos={colectivos.datos} />
      ) : (
        <CentroControl
          antenas={red.datos?.antenas ?? []}
          zonas={red.datos?.zonas ?? []}
          colectivos={colectivos.datos ?? []}
          cargando={!red.datos && !red.error}
          refrescarRed={red.refrescar}
        />
      )}
    </div>
  );
}
