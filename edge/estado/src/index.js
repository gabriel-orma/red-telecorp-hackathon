/**
 * Espejo del estado público de Red TeleCorp en Cloudflare Workers + KV (tercera nube, decisión D15).
 *
 *   PUT  /publicar            AWS (barrido del motor, cada 5 min) publica el estado. Requiere `Authorization: Bearer <token>`.
 *   GET  /api/estado?zonaId=  Mismo contrato que el API de AWS (contracts/schemas/estado-red.schema.json) + campo `respaldo`.
 *   GET  /salud               Sonda para el panel «Nubes» de AWS: lee KV, no escribe.
 *   GET  /                    Página de estado propia: sigue en línea aunque AWS no responda.
 *
 * Bindings (wrangler): KV `ESTADO` y secreto `TOKEN_PUBLICACION`. Plan gratuito: 100 000 pedidos y 1000 escrituras de KV al día;
 * AWS escribe como mucho una vez cada 4 min (≤ 360/día).
 */
import { PAGINA } from "./pagina.js";

export const CLAVE = "estado";
export const MAX_BYTES = 1_000_000;
const ZONA = /^ZONA-\d{2}$/;

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, OPTIONS",
  "access-control-allow-headers": "content-type",
};

export function json(datos, status = 200, extra = {}) {
  return new Response(JSON.stringify(datos), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...CORS, ...extra },
  });
}

/** Comparación en tiempo constante (no revela cuántos caracteres del token coinciden). */
export function mismoToken(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || !b) return false;
  const x = new TextEncoder().encode(a), y = new TextEncoder().encode(b);
  let diferencia = x.length ^ y.length;
  for (let i = 0; i < y.length; i++) diferencia |= (x[i] ?? 0) ^ y[i];
  return diferencia === 0;
}

/** Valida lo que publica AWS. Devuelve un mensaje de error o null. */
export function validarPublicacion(p) {
  if (!p || typeof p !== "object") return "cuerpo inválido";
  if (p.version !== 1) return "versión no soportada";
  if (typeof p.publicadoEn !== "string") return "falta publicadoEn";
  const e = p.estados;
  if (!e || typeof e !== "object" || !e.GLOBAL) return "falta el estado GLOBAL";
  for (const [clave, est] of Object.entries(e)) {
    if (clave !== "GLOBAL" && !ZONA.test(clave)) return `alcance inválido: ${clave.slice(0, 20)}`;
    if (!est || typeof est.nivel !== "string" || typeof est.mensaje !== "string") return `estado incompleto: ${clave}`;
  }
  return null;
}

/** El estado de un alcance, marcado como respaldo (para que la interfaz diga de dónde viene y de cuándo es). */
export function estadoDe(publicacion, alcance, ahoraMs = Date.now()) {
  const est = publicacion?.estados?.[alcance];
  if (!est) return null;
  const edadS = Math.max(0, Math.round((ahoraMs - Date.parse(publicacion.publicadoEn)) / 1000));
  return { ...est, respaldo: { fuente: "cloudflare", publicadoEn: publicacion.publicadoEn, edadS } };
}

async function leer(env) {
  // cacheTtl: KV guarda la lectura en el borde 60 s (menos lecturas del cupo gratuito).
  return env.ESTADO.get(CLAVE, { type: "json", cacheTtl: 60 });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const metodo = request.method.toUpperCase();

    if (metodo === "OPTIONS") return new Response(null, { status: 204, headers: CORS });

    if (url.pathname === "/publicar") {
      if (metodo !== "PUT") return json({ error: "Método no permitido" }, 405);
      const auth = request.headers.get("authorization") || "";
      if (!mismoToken(auth.replace(/^Bearer\s+/i, ""), env.TOKEN_PUBLICACION)) return json({ error: "No autorizado" }, 401);
      const largo = Number(request.headers.get("content-length") || 0);
      if (largo > MAX_BYTES) return json({ error: "Demasiado grande" }, 413);
      const texto = await request.text();
      if (texto.length > MAX_BYTES) return json({ error: "Demasiado grande" }, 413);
      let publicacion;
      try { publicacion = JSON.parse(texto); } catch { return json({ error: "JSON inválido" }, 400); }
      const error = validarPublicacion(publicacion);
      if (error) return json({ error }, 400);
      await env.ESTADO.put(CLAVE, texto);
      return json({ ok: true, alcances: Object.keys(publicacion.estados).length });
    }

    if (metodo !== "GET" && metodo !== "HEAD") return json({ error: "Método no permitido" }, 405);

    if (url.pathname === "/salud") {
      const p = await leer(env);
      return json({ ok: true, publicadoEn: p?.publicadoEn ?? null,
                    edadS: p ? Math.round((Date.now() - Date.parse(p.publicadoEn)) / 1000) : null });
    }

    if (url.pathname === "/api/estado") {
      const alcance = url.searchParams.get("zonaId") || "GLOBAL";
      if (alcance !== "GLOBAL" && !ZONA.test(alcance)) return json({ error: `Zona desconocida: ${alcance.slice(0, 20)}` }, 404);
      const p = await leer(env);
      if (!p) return json({ error: "Aún no hay un estado publicado" }, 503);
      const est = estadoDe(p, alcance);
      if (!est) return json({ error: `Zona desconocida: ${alcance}` }, 404);
      return json(est, 200, { "cache-control": "public, max-age=30" });
    }

    if (url.pathname === "/" || url.pathname === "/index.html") {
      return new Response(PAGINA, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "public, max-age=300" } });
    }

    return json({ error: "No encontrado" }, 404);
  },
};
