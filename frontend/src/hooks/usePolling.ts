import { useCallback, useEffect, useRef, useState } from "react";

/** Llama a `cargar` cada `ms` (pausado si la pestaña está oculta). Mantiene el último dato bueno ante errores.
 *
 * A prueba de cambios rápidos (simulación acelerada + WebSocket):
 * - **Un solo pedido a la vez**: si llega otro aviso mientras hay uno en vuelo, se agenda UNA recarga más al terminar
 *   (nunca se apilan pedidos ni una respuesta vieja pisa a una nueva).
 * - Tras desmontar el componente, las respuestas que lleguen se descartan.
 */
export function usePolling<T>(cargar: () => Promise<T>, ms: number) {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ultimaCarga, setUltimaCarga] = useState<number | null>(null);
  const ref = useRef(cargar);
  ref.current = cargar;
  const enVuelo = useRef<Promise<void> | null>(null);
  const otraVez = useRef(false);
  const montado = useRef(true);

  const refrescar = useCallback((): Promise<void> => {
    if (enVuelo.current) { otraVez.current = true; return enVuelo.current; }
    const ciclo = (async () => {
      do {
        otraVez.current = false;
        try {
          const d = await ref.current();
          if (!montado.current) return;
          setDatos(d);
          setError(null);
          setUltimaCarga(Date.now());
        } catch (e) {
          if (montado.current) setError(e instanceof Error ? e.message : String(e));
        }
      } while (otraVez.current && montado.current);
    })().finally(() => { enVuelo.current = null; });
    enVuelo.current = ciclo;
    return ciclo;
  }, []);

  // `cargar` está en las dependencias: al cambiar la zona o el rango (los llamadores usan useCallback) se recarga de inmediato.
  useEffect(() => {
    montado.current = true;
    refrescar();
    const id = setInterval(() => {
      if (document.visibilityState === "visible") refrescar();
    }, ms);
    return () => { clearInterval(id); montado.current = false; };
  }, [ms, refrescar, cargar]);

  return { datos, error, ultimaCarga, refrescar };
}
