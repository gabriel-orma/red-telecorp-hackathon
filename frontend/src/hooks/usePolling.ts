import { useCallback, useEffect, useRef, useState } from "react";

/** Llama a `cargar` cada `ms` (pausado si la pestaña está oculta). Mantiene el último dato bueno ante errores. */
export function usePolling<T>(cargar: () => Promise<T>, ms: number) {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ultimaCarga, setUltimaCarga] = useState<number | null>(null);
  const ref = useRef(cargar);
  ref.current = cargar;

  const refrescar = useCallback(async () => {
    try {
      setDatos(await ref.current());
      setError(null);
      setUltimaCarga(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    refrescar();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") refrescar();
    }, ms);
    return () => clearInterval(id);
  }, [ms, refrescar]);

  return { datos, error, ultimaCarga, refrescar };
}
