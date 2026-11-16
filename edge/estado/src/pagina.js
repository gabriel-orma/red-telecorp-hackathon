/** Página de estado servida por el Worker: HTML + JS sin dependencias. Lee `/api/estado` del mismo Worker. */
export const PAGINA = `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Estado de Red TeleCorp</title>
<style>
  :root { --fondo:#f4f6f8; --tarjeta:#fff; --texto:#17202a; --tenue:#5d6d7e; --borde:#dfe4ea;
          --ok:#1e8449; --aviso:#b9770e; --mal:#c0392b; }
  @media (prefers-color-scheme: dark) {
    :root { --fondo:#0f1419; --tarjeta:#18202a; --texto:#e8edf2; --tenue:#93a1b0; --borde:#2a3542;
            --ok:#52be80; --aviso:#f5b041; --mal:#ec7063; }
  }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; background:var(--fondo); color:var(--texto); }
  main { max-width: 720px; margin: 0 auto; padding: 24px 16px 48px; }
  h1 { font-size: 1.5rem; margin: 0 0 4px; }
  .tenue { color: var(--tenue); font-size: .875rem; }
  .tarjeta { background: var(--tarjeta); border: 1px solid var(--borde); border-radius: 14px; padding: 18px; margin-top: 16px; }
  .semaforo { display:flex; gap:14px; align-items:center; }
  .luz { width: 22px; height: 22px; border-radius: 50%; flex: none; background: var(--tenue); }
  .SIN_PROBLEMAS .luz { background: var(--ok); } .POSIBLES_PROBLEMAS .luz { background: var(--aviso); } .PROBLEMAS .luz { background: var(--mal); }
  .titulo { font-size: 1.15rem; font-weight: 650; }
  select { font: inherit; padding: 8px 10px; border-radius: 10px; border: 1px solid var(--borde); background: var(--tarjeta); color: var(--texto); width: 100%; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { display:flex; justify-content: space-between; gap: 12px; padding: 8px 0; border-top: 1px solid var(--borde); }
  li:first-child { border-top: 0; }
  .etiqueta { font-size: .75rem; padding: 2px 8px; border-radius: 99px; border: 1px solid var(--borde); white-space: nowrap; }
  .aviso { border-left: 4px solid var(--aviso); }
  h2 { font-size: 1rem; margin: 0 0 8px; }
</style>
</head>
<body>
<main>
  <h1>Estado de Red TeleCorp</h1>
  <div class="tenue">Copia del estado de la red servida por Cloudflare. Sigue disponible aunque la plataforma principal no responda.</div>

  <div class="tarjeta">
    <label class="tenue" for="zona">Ver el estado de</label>
    <select id="zona"><option value="">Toda la red</option></select>
  </div>

  <div id="estado" class="tarjeta semaforo"><span class="luz"></span><div><div class="titulo">Consultando…</div><div class="tenue" id="mensaje"></div></div></div>
  <div id="frescura" class="tenue" style="margin-top:8px"></div>

  <div class="tarjeta"><h2>Incidentes activos</h2><ul id="colectivos"><li class="tenue">—</li></ul></div>
  <div class="tarjeta"><h2>Zonas con más reportes (24 h)</h2><ul id="zonas"><li class="tenue">—</li></ul></div>
</main>
<script>
  const TITULOS = { SIN_PROBLEMAS: "Sin problemas", POSIBLES_PROBLEMAS: "Posibles problemas", PROBLEMAS: "Problemas confirmados" };
  const NIVEL_ZONA = { SIN_PROBLEMAS: "Normal", POSIBLES_PROBLEMAS: "Posibles problemas", PROBLEMAS: "Problemas" };
  const $ = (id) => document.getElementById(id);
  const texto = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;" }[c]));
  const hace = (s) => s < 90 ? "hace un momento" : s < 3600 ? "hace " + Math.round(s / 60) + " min" : "hace " + Math.round(s / 3600) + " h";
  let zonasCargadas = false;

  async function cargar() {
    const zona = $("zona").value;
    try {
      const r = await fetch("/api/estado" + (zona ? "?zonaId=" + encodeURIComponent(zona) : ""));
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
      $("estado").className = "tarjeta semaforo " + d.nivel;
      $("estado").querySelector(".titulo").textContent = TITULOS[d.nivel] || d.nivel;
      $("mensaje").textContent = d.mensaje;
      const edad = d.respaldo ? d.respaldo.edadS : 0;
      $("frescura").textContent = "Datos publicados " + hace(edad) + (edad > 900 ? " · la plataforma principal no ha enviado datos recientes" : "");
      $("colectivos").innerHTML = d.colectivos.length
        ? d.colectivos.map((c) => "<li><span>" + texto(c.nombre) + "</span><span class='etiqueta'>" + texto(c.afectados) + " afectados</span></li>").join("")
        : "<li class='tenue'>No hay incidentes confirmados.</li>";
      $("zonas").innerHTML = d.zonas.slice(0, 8).map((z) =>
        "<li><span>" + texto(z.nombre) + " <span class='tenue'>· " + texto(z.total24h) + " reportes</span></span><span class='etiqueta'>" + texto(NIVEL_ZONA[z.nivel] || z.nivel) + "</span></li>").join("");
      if (!zonasCargadas) {
        zonasCargadas = true;
        [...d.zonas].sort((a, b) => a.nombre.localeCompare(b.nombre)).forEach((z) => $("zona").add(new Option(z.nombre, z.zonaId)));
      }
    } catch (e) {
      $("estado").className = "tarjeta semaforo aviso";
      $("estado").querySelector(".titulo").textContent = "No pudimos leer el estado";
      $("mensaje").textContent = "Reintentando en unos segundos.";
    }
  }
  $("zona").addEventListener("change", cargar);
  cargar();
  setInterval(cargar, 60000);
</script>
</body>
</html>`;
