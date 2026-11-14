import { useCallback, useState } from "react";
import { Toaster } from "sonner";
import { api, apiColectivos } from "./lib/api";
import { navegar, useRuta } from "./lib/router";
import { useAlCambiar, useConexionTiempoReal } from "./lib/tiempoReal";
import { usePolling } from "./hooks/usePolling";
import { PanelIncidencias } from "./pages/PanelIncidencias";
import { EstadoPublico } from "./pages/EstadoPublico";
import { Cuenta } from "./pages/Cuenta";
import { Reportar } from "./pages/Reportar";
import { Seguimiento } from "./pages/Seguimiento";
import { Colectivos } from "./pages/Colectivos";
import { MapaNeu } from "./pages/MapaNeu";
import { LineaTiempoNeu } from "./pages/LineaTiempoNeu";
import { Analitica } from "./pages/Analitica";
import { ShellNeu } from "./components/neu/ShellNeu";
import { PaletaComandos } from "./components/neu/PaletaComandos";
import { useAlertasColectivos } from "./components/neu/alertas";

// Con WebSocket los datos llegan al instante: el polling queda como respaldo lento. Sin WebSocket, polling rápido.
const POLLING_RAPIDO_MS = 3000;
const POLLING_RESPALDO_MS = 30_000;

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

const TITULOS: Record<string, string> = { "/incidencias": "Incidencias", "/colectivos": "Incidentes colectivos", "/analitica": "Analítica operativa" };

function Operador({ ruta }: { ruta: string }) {
  const tiempoReal = useConexionTiempoReal();
  const POLLING_MS = tiempoReal ? POLLING_RESPALDO_MS : POLLING_RAPIDO_MS;
  const red = usePolling(
    useCallback(async () => {
      const [a, z] = await Promise.all([api.antenas(), api.zonas()]);
      return { antenas: a.antenas, zonas: z.zonas };
    }, []),
    POLLING_MS,
  );
  const colectivos = usePolling(useCallback(() => apiColectivos.listar().then((r) => r.colectivos), []), POLLING_MS);
  const [buscar, setBuscar] = useState(false);
  useAlCambiar(["antenas"], red.refrescar);
  useAlCambiar(["colectivos"], colectivos.refrescar);
  useAlertasColectivos(colectivos.datos ?? [], colectivos.datos !== null);

  const antenas = red.datos?.antenas ?? [];
  const zonas = red.datos?.zonas ?? [];
  const lista = colectivos.datos ?? [];
  const enVivo = !red.error && red.ultimaCarga !== null;
  const activos = lista.filter((c) => c.estado !== "CERRADO" && c.estado !== "SERVICIO_RESTABLECIDO").length;

  return (
    <div className="tema-neu h-full">
      <Toaster position="top-center" theme="dark" visibleToasts={3} toastOptions={{ unstyled: true }} />
      {ruta in TITULOS ? (
        <ShellNeu titulo={TITULOS[ruta]} enVivo={enVivo} colectivosActivos={activos} onBuscar={() => setBuscar(true)}>
          <PaletaComandos abierta={buscar} onAbrir={() => setBuscar(true)} onCerrar={() => setBuscar(false)} zonas={zonas} antenas={antenas}
            onZona={(z) => navegar(`/?zona=${z.zonaId}`)} onAntena={(a) => navegar(`/?antena=${a.antenaId}`)} />
          {ruta === "/incidencias" ? <PanelIncidencias zonas={zonas} />
            : ruta === "/analitica" ? <Analitica /> : <Colectivos abiertos={colectivos.datos} />}
        </ShellNeu>
      ) : ruta === "/linea-tiempo" ? (
        <LineaTiempoNeu antenas={antenas} zonas={zonas} colectivosActivos={activos} enVivo={enVivo} refrescarRed={red.refrescar} />
      ) : (
        <MapaNeu antenas={antenas} zonas={zonas} colectivos={lista} enVivo={enVivo} refrescarRed={red.refrescar} />
      )}
    </div>
  );
}
