// Presupuesto de concurrencia (decisión D14): AWS Academy desactiva la cuenta si hay más de 10 Lambdas ejecutándose a la vez,
// y el API tiene un tope de 2. Este módulo hace que el navegador nunca tenga más de 2 pedidos al API en vuelo (los demás
// esperan en fila) y reintenta con espera creciente cuando el API responde "ocupado" (429/502/503/504 o el 500 que
// API Gateway devuelve cuando la Lambda está al tope).
const MAX_EN_VUELO = 2;
const REINTENTOS = 4;
let enVuelo = 0;
const fila: (() => void)[] = [];

async function turno(): Promise<() => void> {
  if (enVuelo >= MAX_EN_VUELO) await new Promise<void>((r) => fila.push(r));
  enVuelo++;
  let liberado = false;
  return () => {
    if (liberado) return;
    liberado = true;
    enVuelo--;
    fila.shift()?.();
  };
}

const esperar = (ms: number) => new Promise((r) => setTimeout(r, ms));
const OCUPADO = new Set([429, 500, 502, 503, 504]);

/** fetch al API con cupo y reintentos. Un 500 con cuerpo `{"error": ...}` es un error real del handler: no se reintenta. */
export async function fetchApi(url: string, init?: RequestInit): Promise<Response> {
  for (let intento = 0; ; intento++) {
    const liberar = await turno();
    let r: Response;
    try {
      r = await fetch(url, init);
    } catch (e) {
      liberar();
      if (intento >= REINTENTOS) throw e;
      await esperar(400 * 2 ** intento + Math.random() * 300);
      continue;
    }
    liberar();
    if (!OCUPADO.has(r.status) || intento >= REINTENTOS) return r;
    if (r.status === 500) {
      // API Gateway al tope responde {"message":"Internal Server Error"}; nuestros handlers usan {"error": ...}.
      const cuerpo = await r.clone().json().catch(() => ({}));
      if (cuerpo && typeof cuerpo === "object" && "error" in cuerpo) return r;
    }
    await esperar(400 * 2 ** intento + Math.random() * 300);
  }
}
