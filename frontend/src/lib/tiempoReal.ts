// Tiempo real (E7): una conexión WebSocket compartida por todo el panel.
// El servidor solo avisa QUÉ cambió ({tipo: "antenas" | "colectivos" | "incidencias"}); el panel vuelve a pedir esos datos.
// Si la conexión se cae, se reintenta con espera creciente y, mientras tanto, el polling sigue funcionando.
import { useEffect, useRef, useState } from "react";

export type TipoAviso = "antenas" | "colectivos" | "incidencias";
type Oyente = (tipo: TipoAviso) => void;

const oyentes = new Set<Oyente>();
const oyentesEstado = new Set<(c: boolean) => void>();
let socket: WebSocket | null = null;
let conectado = false;
let intentos = 0;
let ping: ReturnType<typeof setInterval> | null = null;
let iniciado = false;

function avisarEstado(c: boolean) {
  conectado = c;
  oyentesEstado.forEach((f) => f(c));
}

async function conectar() {
  let url: string | undefined;
  try { url = (await fetch("/api/config").then((r) => r.json())).wsUrl; } catch { /* sin API: reintentar */ }
  if (!url) return reintentar();
  socket = new WebSocket(url);
  socket.onopen = () => {
    intentos = 0;
    avisarEstado(true);
    ping = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send(JSON.stringify({ accion: "ping" })), 4 * 60_000);
  };
  socket.onmessage = (e) => {
    try {
      const m = JSON.parse(e.data);
      if (m.tipo === "antenas" || m.tipo === "colectivos" || m.tipo === "incidencias") oyentes.forEach((f) => f(m.tipo));
    } catch { /* mensaje no JSON */ }
  };
  socket.onclose = () => {
    if (ping) clearInterval(ping);
    avisarEstado(false);
    reintentar();
  };
}

function reintentar() {
  intentos += 1;
  setTimeout(conectar, Math.min(30_000, 1000 * 2 ** Math.min(intentos, 5)));
}

function iniciar() {
  if (iniciado) return;
  iniciado = true;
  conectar();
}

/** Estado de la conexión WebSocket (inicia la conexión la primera vez). */
export function useConexionTiempoReal(): boolean {
  const [c, setC] = useState(conectado);
  useEffect(() => {
    iniciar();
    oyentesEstado.add(setC);
    return () => { oyentesEstado.delete(setC); };
  }, []);
  return c;
}

/** Ejecuta `fn` cada vez que el servidor avisa un cambio de alguno de los `tipos` (con un pequeño agrupamiento). */
export function useAlCambiar(tipos: TipoAviso[], fn: () => void) {
  const ref = useRef(fn);
  ref.current = fn;
  const clave = tipos.join(",");
  useEffect(() => {
    iniciar();
    let t: ReturnType<typeof setTimeout> | null = null;
    const oyente: Oyente = (tipo) => {
      if (!clave.split(",").includes(tipo)) return;
      if (t) clearTimeout(t);
      t = setTimeout(() => ref.current(), 250);
    };
    oyentes.add(oyente);
    return () => { oyentes.delete(oyente); if (t) clearTimeout(t); };
  }, [clave]);
}
