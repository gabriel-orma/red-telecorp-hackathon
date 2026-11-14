import { useEffect, useRef, useState } from "react";

/** Número que se desliza suavemente hacia su nuevo valor (contadores del panel). */
export function NumeroAnimado({ valor, decimales = 0, duracion = 700 }: { valor: number; decimales?: number; duracion?: number }) {
  const [mostrado, setMostrado] = useState(valor);
  const desde = useRef(valor);

  useEffect(() => {
    const inicio = performance.now();
    const origen = desde.current;
    let frame = 0;
    const paso = (t: number) => {
      const p = Math.min(1, (t - inicio) / duracion);
      const suave = 1 - Math.pow(1 - p, 3);
      const actual = origen + (valor - origen) * suave;
      setMostrado(actual);
      desde.current = actual;
      if (p < 1) frame = requestAnimationFrame(paso);
    };
    frame = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(frame);
  }, [valor, duracion]);

  return <>{mostrado.toLocaleString("es-PE", { minimumFractionDigits: decimales, maximumFractionDigits: decimales })}</>;
}
