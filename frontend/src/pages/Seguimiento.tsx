import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowLeft, Copy, Loader2, Radio, Users } from "lucide-react";
import { apiIncidencias, type DetalleIncidencia } from "../lib/api";
import { ESTADO, ESTADO_INCIDENCIA, TIPO_PROBLEMA, TIPO_ZONA } from "../lib/estados";
import { enlace } from "../lib/router";
import { haceCuanto } from "../lib/utils";
import { Historial, Progreso } from "../components/LineaTiempo";
import { PortalLayout } from "../components/PortalLayout";

export function Seguimiento({ incidenciaId }: { incidenciaId: string }) {
  const [det, setDet] = useState<DetalleIncidencia | null>(null);
  const [error, setError] = useState<string | null>(null);
  const duplicado = new URLSearchParams(window.location.search).has("duplicado");

  // Polling: recién creada puede tardar 1–2 s en registrarse (pasa por SQS), así que un 404 inicial es normal.
  const cargar = useCallback(async () => {
    try { setDet(await apiIncidencias.obtener(incidenciaId)); setError(null); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }, [incidenciaId]);
  useEffect(() => {
    cargar();
    const t = setInterval(cargar, 4000);
    return () => clearInterval(t);
  }, [cargar]);

  if (!det) {
    return (
      <PortalLayout>
        <div className="grid h-72 place-items-center text-center text-sm text-tenue">
          <div>
            <Loader2 className="mx-auto mb-3 size-6 animate-spin text-acento" />
            {error ? "Registrando tu reporte…" : "Cargando seguimiento…"}
            <div className="cifra mt-1 text-[11px]">{incidenciaId}</div>
          </div>
        </div>
      </PortalLayout>
    );
  }

  const { incidencia: inc, zona, historial } = det;
  const est = ESTADO_INCIDENCIA[inc.estado];
  const Tipo = TIPO_PROBLEMA[inc.tipo]?.icono ?? TIPO_PROBLEMA.OTRO.icono;
  const redColor = ESTADO[zona.estadoRed].color;

  return (
    <PortalLayout>
      <a {...enlace("/portal")} className="mb-4 inline-flex items-center gap-1 text-xs text-tenue hover:text-texto"><ArrowLeft className="size-3.5" /> Nuevo reporte</a>

      {duplicado && (
        <div className="mb-3 rounded-xl bg-saturada/10 px-4 py-3 text-xs text-saturada ring-1 ring-saturada/30">
          Ya tenías un reporte activo en esta zona, así que no creamos otro: este es su seguimiento.
        </div>
      )}

      {/* Estado actual */}
      <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="panel overflow-hidden">
        <div className="p-5" style={{ background: `linear-gradient(135deg, ${est.color}22, transparent 60%)` }}>
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-xs text-tenue"><Tipo className="size-4" /> {TIPO_PROBLEMA[inc.tipo]?.etiqueta}</span>
            <button onClick={() => navigator.clipboard?.writeText(inc.incidenciaId)} className="cifra flex items-center gap-1 text-[10px] text-tenue hover:text-texto" title="Copiar código">
              {inc.incidenciaId} <Copy className="size-3" />
            </button>
          </div>
          <div className="mt-3 text-2xl font-semibold" style={{ color: est.color }}>{est.etiqueta}</div>
          <div className="text-sm text-tenue">{est.ayuda} · actualizado {haceCuanto(inc.actualizadaEn)}</div>
          <div className="mt-6"><Progreso estado={inc.estado} /></div>
        </div>
      </motion.section>

      {/* Estado de la zona */}
      <section className="panel mt-3 p-4">
        <div className="mb-3 text-[11px] uppercase tracking-wider text-tenue">Tu zona · {zona.nombre} · {TIPO_ZONA[zona.tipo]?.etiqueta}</div>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="rounded-xl bg-fondo/60 p-3">
            <Radio className="mx-auto mb-1 size-4" style={{ color: redColor }} />
            <div className="text-sm font-semibold" style={{ color: redColor }}>{ESTADO[zona.estadoRed].etiqueta}</div>
            <div className="text-[10px] text-tenue">red de la zona</div>
          </div>
          <div className="rounded-xl bg-fondo/60 p-3">
            <Users className="mx-auto mb-1 size-4 text-acento" />
            <div className="cifra text-sm font-semibold">{zona.usuariosAfectados24h}</div>
            <div className="text-[10px] text-tenue">vecinos reportaron (24 h)</div>
          </div>
          <div className="rounded-xl bg-fondo/60 p-3">
            <AlertTriangle className="mx-auto mb-1 size-4" style={{ color: zona.antenasConFalla ? ESTADO.CAIDA.color : ESTADO.NORMAL.color }} />
            <div className="cifra text-sm font-semibold">{zona.antenasConFalla}</div>
            <div className="text-[10px] text-tenue">antenas con falla</div>
          </div>
        </div>
        {zona.antenasConFalla > 0 && (
          <p className="mt-3 text-xs text-caida">Detectamos una falla en la infraestructura de tu zona. Nuestro equipo ya fue alertado.</p>
        )}
      </section>

      {/* Historial */}
      <section className="panel mt-3 p-4">
        <div className="mb-3 text-[11px] uppercase tracking-wider text-tenue">Historial</div>
        <Historial eventos={historial} />
      </section>
    </PortalLayout>
  );
}
