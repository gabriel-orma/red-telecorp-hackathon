import { useCallback, useState } from "react";
import { api, type Antena, type EstadoSimulador, type Zona } from "./lib/api";
import { usePolling } from "./hooks/usePolling";
import { Encabezado } from "./components/Encabezado";
import { PanelLateral } from "./components/PanelLateral";
import { MapaRed } from "./components/MapaRed";
import { DetalleAntena } from "./components/DetalleAntena";
import { PanelSimulador } from "./components/PanelSimulador";
import { Leyenda } from "./components/Leyenda";

const POLLING_MS = 3000;

export default function App() {
  const red = usePolling(
    useCallback(async () => {
      const [a, z] = await Promise.all([api.antenas(), api.zonas()]);
      return { antenas: a.antenas, zonas: z.zonas };
    }, []),
    POLLING_MS,
  );
  const sim = usePolling<EstadoSimulador>(api.simulador, 10_000);

  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [zonaFoco, setZonaFoco] = useState<Zona | null>(null);

  const antenas: Antena[] = red.datos?.antenas ?? [];
  const zonas: Zona[] = red.datos?.zonas ?? [];
  const antenaSel = antenas.find((a) => a.antenaId === seleccion) ?? null;

  const cambiarSimulador = async (cambios: Parameters<typeof api.actualizarSimulador>[0]) => {
    await api.actualizarSimulador(cambios);
    await sim.refrescar();
    setTimeout(red.refrescar, 1500); // la muestra inmediata tarda ~1 s en clasificarse
  };

  return (
    <div className="fondo-rejilla flex h-full flex-col">
      <Encabezado ultimaCarga={red.ultimaCarga} error={red.error} />
      <main className="flex min-h-0 flex-1 flex-col-reverse md:flex-row">
        <PanelLateral antenas={antenas} zonas={zonas} onZona={setZonaFoco} />
        <div className="relative h-[52vh] shrink-0 overflow-hidden md:m-3 md:ml-0 md:h-auto md:flex-1 md:rounded-2xl md:border md:border-borde">
          <MapaRed antenas={antenas} zonas={zonas} seleccion={seleccion} onSeleccionar={setSeleccion} enfocarZona={zonaFoco} />
          <PanelSimulador estado={sim.datos} onCambiar={cambiarSimulador} />
          <DetalleAntena
            antena={antenaSel}
            zona={zonas.find((z) => z.zonaId === antenaSel?.zonaId)}
            forzada={antenaSel ? sim.datos?.fallas[antenaSel.antenaId] : undefined}
            onCerrar={() => setSeleccion(null)}
            onForzar={(id, valor) => cambiarSimulador({ fallas: { [id]: valor } })}
          />
          <Leyenda />
          {!red.datos && !red.error && (
            <div className="absolute inset-0 grid place-items-center text-sm text-tenue">Conectando con la red…</div>
          )}
        </div>
      </main>
    </div>
  );
}
