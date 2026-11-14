import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { cn } from "../lib/utils";

// Web Speech API (Chrome, Edge, Safari): no está en los tipos de TypeScript del DOM.
type Reconocedor = {
  lang: string; interimResults: boolean; continuous: boolean;
  onresult: (e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>; resultIndex: number }) => void;
  onend: () => void; onerror: (e: { error: string }) => void; start: () => void; stop: () => void;
};
const Constructor = (window as unknown as { SpeechRecognition?: new () => Reconocedor; webkitSpeechRecognition?: new () => Reconocedor })
  .SpeechRecognition ?? (window as unknown as { webkitSpeechRecognition?: new () => Reconocedor }).webkitSpeechRecognition;

/** Botón para dictar la descripción del reporte (reporte por voz, E7). Si el navegador no lo soporta, no se muestra. */
export function Dictado({ texto, onTexto }: { texto: string; onTexto: (t: string) => void }) {
  const [escuchando, setEscuchando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Reconocedor | null>(null);
  const base = useRef("");

  useEffect(() => () => rec.current?.stop(), []);
  if (!Constructor) return null;

  const alternar = () => {
    if (escuchando) { rec.current?.stop(); return; }
    setError(null);
    const r = new Constructor();
    r.lang = "es-PE";
    r.interimResults = true;
    r.continuous = true;
    base.current = texto ? texto.trimEnd() + " " : "";
    r.onresult = (e) => {
      let dicho = "";
      for (let i = 0; i < e.results.length; i++) dicho += e.results[i][0].transcript;
      onTexto((base.current + dicho).slice(0, 2000));
    };
    r.onerror = (e) => setError(e.error === "not-allowed" ? "Permite el micrófono para dictar." : "No se pudo usar el micrófono.");
    r.onend = () => setEscuchando(false);
    rec.current = r;
    r.start();
    setEscuchando(true);
  };

  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={alternar} aria-label={escuchando ? "Detener dictado" : "Dictar por voz"} aria-pressed={escuchando}
        className={cn("flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium transition-colors",
          escuchando ? "degradado text-white" : "boton-neu text-tenue")}>
        {escuchando ? <Square className="size-3.5" /> : <Mic className="size-3.5" />}
        {escuchando ? "Escuchando… toca para terminar" : "Dictar por voz"}
      </button>
      {escuchando && <span className="latido size-2 rounded-full bg-caida" />}
      {error && <span className="text-[11px] text-caida">{error}</span>}
    </div>
  );
}
