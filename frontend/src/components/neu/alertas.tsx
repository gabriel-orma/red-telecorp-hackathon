import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { Siren } from "lucide-react";
import type { Colectivo } from "../../lib/api";
import { navegar } from "../../lib/router";

/** Aviso (Sonner) cuando aparece un incidente colectivo nuevo. La primera carga solo registra los existentes. */
export function useAlertasColectivos(colectivos: Colectivo[], listos: boolean) {
  const vistos = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!listos) return;
    if (vistos.current === null) { vistos.current = new Set(colectivos.map((c) => c.incidenteColectivoId)); return; }
    const nuevos = colectivos.filter((c) => !vistos.current!.has(c.incidenteColectivoId));
    nuevos.forEach((c) => vistos.current!.add(c.incidenteColectivoId));
    // Varios a la vez (simulación acelerada): un solo aviso agrupado en lugar de una pila de toasts.
    if (nuevos.length > 2) {
      toast.custom((t) => (
        <button onClick={() => { toast.dismiss(t); navegar("/colectivos"); }}
          className="tema-neu neu flex w-[min(420px,calc(100vw-32px))] items-center gap-3 p-3 text-left">
          <span className="degradado grid size-10 shrink-0 place-items-center rounded-2xl text-white"><Siren className="size-5" /></span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold">{nuevos.length} incidentes colectivos nuevos</span>
            <span className="block truncate text-xs text-tenue">{nuevos.map((c) => c.zona.nombre).join(" · ")}</span>
          </span>
        </button>
      ), { id: "colectivos-agrupados", duration: 10_000 });
      return;
    }
    for (const c of nuevos) {
      toast.custom((t) => (
        <button onClick={() => { toast.dismiss(t); navegar(`/colectivos?id=${c.incidenteColectivoId}`); }}
          className="tema-neu neu flex w-[min(420px,calc(100vw-32px))] items-center gap-3 p-3 text-left">
          <span className="degradado grid size-10 shrink-0 place-items-center rounded-2xl text-white"><Siren className="size-5" /></span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold">Incidente colectivo detectado</span>
            <span className="block truncate text-xs text-tenue">{c.zona.nombre} · {c.origenDetalle}</span>
          </span>
        </button>
      ), { id: c.incidenteColectivoId, duration: 12_000 });
    }
  }, [colectivos, listos]);
}
