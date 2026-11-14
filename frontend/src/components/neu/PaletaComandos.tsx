import { useEffect } from "react";
import { Command } from "cmdk";
import { MapPin, Radio, Route } from "lucide-react";
import type { Antena, Zona } from "../../lib/api";
import { ESTADO, TIPO_ZONA } from "../../lib/estados";
import { navegar } from "../../lib/router";

interface Props {
  abierta: boolean;
  onCerrar: () => void;
  onAbrir: () => void;
  zonas: Zona[];
  antenas: Antena[];
  onZona: (z: Zona) => void;
  onAntena: (a: Antena) => void;
}

const PAGINAS = [
  { ruta: "/incidencias", etiqueta: "Ir a incidencias" },
  { ruta: "/colectivos", etiqueta: "Ir a incidentes colectivos" },
  { ruta: "/analitica", etiqueta: "Ir a analítica operativa" },
  { ruta: "/portal", etiqueta: "Ir al estado público" },
];

/** Paleta Ctrl+K (cmdk): buscar zonas, antenas y pantallas. */
export function PaletaComandos({ abierta, onCerrar, onAbrir, zonas, antenas, onZona, onAntena }: Props) {
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); abierta ? onCerrar() : onAbrir(); }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [abierta, onAbrir, onCerrar]);

  const elegir = (accion: () => void) => { accion(); onCerrar(); };

  return (
    <Command.Dialog open={abierta} onOpenChange={(v) => (v ? onAbrir() : onCerrar())} label="Buscar"
      overlayClassName="fixed inset-0 z-40 bg-black/45 backdrop-blur-[2px]"
      contentClassName="tema-neu neu fixed left-1/2 top-[14vh] z-50 w-[min(560px,calc(100%-24px))] -translate-x-1/2 overflow-hidden p-2">
      <Command.Input autoFocus placeholder="Buscar antena, zona o pantalla…"
        className="neu-hundido w-full px-4 py-3 text-sm text-texto outline-none placeholder:text-tenue" />
      <Command.List className="scroll-fino mt-2 max-h-[50vh] overflow-y-auto px-1 pb-1">
        <Command.Empty className="px-3 py-6 text-center text-sm text-tenue">Sin resultados.</Command.Empty>
        <Grupo titulo="Zonas">
          {zonas.map((z) => {
            const Icono = TIPO_ZONA[z.tipo].icono;
            return (
              <Item key={z.zonaId} valor={`${z.nombre} ${z.zonaId} ${TIPO_ZONA[z.tipo].etiqueta}`} onSelect={() => elegir(() => onZona(z))}>
                <Icono className="size-4 text-tenue" /> {z.nombre}
                <span className="ml-auto text-[11px]" style={{ color: ESTADO[z.estado].color }}>{ESTADO[z.estado].etiqueta}</span>
              </Item>
            );
          })}
        </Grupo>
        <Grupo titulo="Antenas">
          {antenas.map((a) => (
            <Item key={a.antenaId} valor={`${a.antenaId} ${zonas.find((z) => z.zonaId === a.zonaId)?.nombre ?? ""}`} onSelect={() => elegir(() => onAntena(a))}>
              <Radio className="size-4 text-tenue" /> <span className="cifra">{a.antenaId}</span>
              <span className="text-tenue">· {zonas.find((z) => z.zonaId === a.zonaId)?.nombre}</span>
              <span className="ml-auto size-2 rounded-full" style={{ background: ESTADO[a.estado].color }} />
            </Item>
          ))}
        </Grupo>
        <Grupo titulo="Pantallas">
          {PAGINAS.map((p) => (
            <Item key={p.ruta} valor={p.etiqueta} onSelect={() => elegir(() => navegar(p.ruta))}>
              <Route className="size-4 text-tenue" /> {p.etiqueta}
            </Item>
          ))}
        </Grupo>
      </Command.List>
      <div className="flex items-center gap-1.5 px-3 pb-1 pt-2 text-[10px] text-tenue"><MapPin className="size-3" /> Enter para ir · Esc para cerrar</div>
    </Command.Dialog>
  );
}

function Grupo({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <Command.Group heading={titulo}
      className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1 [&_[cmdk-group-heading]]:pt-3 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:text-tenue">
      {children}
    </Command.Group>
  );
}

function Item({ valor, onSelect, children }: { valor: string; onSelect: () => void; children: React.ReactNode }) {
  return (
    <Command.Item value={valor} onSelect={onSelect} className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm text-texto/90">
      {children}
    </Command.Item>
  );
}
