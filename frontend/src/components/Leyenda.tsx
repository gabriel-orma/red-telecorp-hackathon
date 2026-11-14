import { ESTADO, ORDEN_ESTADOS } from "../lib/estados";

export function Leyenda() {
  return (
    <div className="panel absolute bottom-3 left-3 z-10 flex flex-wrap gap-x-4 gap-y-1 px-3 py-2 text-[11px]">
      {ORDEN_ESTADOS.map((e) => (
        <span key={e} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full" style={{ background: ESTADO[e].color, boxShadow: `0 0 8px ${ESTADO[e].color}` }} />
          <span>{ESTADO[e].etiqueta}</span>
          <span className="cifra text-tenue">{ESTADO[e].rango}</span>
        </span>
      ))}
    </div>
  );
}
