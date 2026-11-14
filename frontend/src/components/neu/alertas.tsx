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
    for (const c of colectivos) {
      if (vistos.current.has(c.incidenteColectivoId)) continue;
      vistos.current.add(c.incidenteColectivoId);
      toast.custom((t) => (
        <button onClick={() => { toast.dismiss(t); navegar(`/colectivos?id=${c.incidenteColectivoId}`); }}
          className="tema-neu neu flex w-[min(420px,calc(100vw-32px))] items-center gap-3 p-3 text-left">
          <span className="degradado grid size-10 shrink-0 place-items-center rounded-2xl text-white"><Siren className="size-5" /></span>
          <span className="min-w-0">
            <span className="block text-sm font-semibold">Incidente colectivo detectado</span>
            <span className="block truncate text-xs text-tenue">{c.zona.nombre} · {c.origenDetalle}</span>
          </span>
        </button>
      ), { duration: 12_000 });
    }
  }, [colectivos, listos]);
}
