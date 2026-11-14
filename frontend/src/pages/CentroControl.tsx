import { useCallback, useState } from "react";
import { api, apiIncidencias, type Antena, type Colectivo, type EstadoSimulador, type Incidencia, type Zona } from "../lib/api";
import { usePolling } from "../hooks/usePolling";
import { PanelLateral } from "../components/PanelLateral";
import { MapaRed } from "../components/MapaRed";
import { DetalleAntena } from "../components/DetalleAntena";
import { PanelSimulador } from "../components/PanelSimulador";
import { Leyenda } from "../components/Leyenda";

interface Props {
  antenas: Antena[];
  zonas: Zona[];
  colectivos: Colectivo[];
  cargando: boolean;
  refrescarRed: () => void;
}

export function CentroControl({ antenas, zonas, colectivos, cargando, refrescarRed }: Props) {
  const sim = usePolling<EstadoSimulador>(api.simulador, 10_000);
  const reportes = usePolling<Incidencia[]>(
    useCallback(() => apiIncidencias.listar({ horas: 24 }).then((r) => r.incidencias), []),
    10_000,
  );
  const [verCalor, setVerCalor] = useState(true);
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [zonaFoco, setZonaFoco] = useState<Zona | null>(null);
  const antenaSel = antenas.find((a) => a.antenaId === seleccion) ?? null;

  const cambiarSimulador = async (cambios: Parameters<typeof api.actualizarSimulador>[0]) => {
    await api.actualizarSimulador(cambios);
    await sim.refrescar();
    setTimeout(refrescarRed, 1500); // la muestra inmediata tarda ~1 s en clasificarse
  };

  return (
    <main className="flex min-h-0 flex-1 flex-col-reverse md:flex-row">
      <PanelLateral antenas={antenas} zonas={zonas} colectivos={colectivos} onZona={setZonaFoco} reportes24h={reportes.datos?.length ?? 0} />
      <div className="relative h-[52vh] shrink-0 overflow-hidden md:m-3 md:ml-0 md:h-auto md:flex-1 md:rounded-2xl md:border md:border-borde">
        <MapaRed
          antenas={antenas}
          zonas={zonas}
          colectivos={colectivos}
          reportes={verCalor ? reportes.datos ?? [] : []}
          seleccion={seleccion}
          onSeleccionar={setSeleccion}
          enfocarZona={zonaFoco}
        />
        <PanelSimulador estado={sim.datos} onCambiar={cambiarSimulador} />
        <DetalleAntena
          antena={antenaSel}
          zona={zonas.find((z) => z.zonaId === antenaSel?.zonaId)}
          forzada={antenaSel ? sim.datos?.fallas[antenaSel.antenaId] : undefined}
          onCerrar={() => setSeleccion(null)}
          onForzar={(id, valor) => cambiarSimulador({ fallas: { [id]: valor } })}
        />
        <Leyenda verCalor={verCalor} onVerCalor={setVerCalor} reportes={reportes.datos?.length ?? 0} />
        {cargando && <div className="absolute inset-0 grid place-items-center text-sm text-tenue">Conectando con la red…</div>}
      </div>
    </main>
  );
}
