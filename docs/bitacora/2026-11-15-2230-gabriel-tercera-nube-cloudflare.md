# 2026-11-15 22:30 · Gabriel · Tercera nube: Cloudflare Workers + KV (D15)

## Qué cambió
- **Tercera nube: Cloudflare** ([D15](../decisiones/2026-11-15-tercera-nube-cloudflare.md), issue #48). El estado público se publica en un Worker y sigue en línea aunque AWS caiga.
- **Worker** (`edge/estado/`):
  - `PUT /publicar` (con token), `GET /api/estado` (mismo contrato que AWS, más `respaldo`), `GET /salud`, y `GET /` con una página de estado propia;
  - 7 pruebas con `node --test`.
- **AWS:**
  - El cálculo del estado público pasó a la layer (`telecorp/estado_red.py`), con `calcular_todo()` (global y todas las zonas en una sola lectura). `services/api/src/estado.py` lo usa sin cambiar el contrato.
  - `telecorp/nube2/cloudflare.py`: `publicar()` (cupo de una cada 4 min, disyuntor, tablero) y `sondear()`.
  - `workflows/src/detector.py`: el barrido (cada 5 min) llama a `cloudflare.publicar()`. **Sin Lambdas nuevas** (D14: siguen siendo 7). El motor tiene ahora `TABLA_ESTADISTICAS`.
  - `GET /api/nubes` informa `cloudflare.espejo`.
- **Frontend:**
  - `apiPortal.estado` usa la copia de Cloudflare si AWS no responde, y la página pública lo avisa;
  - la página Nubes tiene una tarjeta de Cloudflare;
  - `VITE_ESPEJO_URL` se fija al compilar (`deploy.sh` la lee del secreto).
- **Scripts:** `scripts/cloudflare.sh <stage>` despliega el Worker y el KV, carga el token y crea el secreto `telecorp/<stage>/cloudflare`.
- **Docs:** D15, `docs/despliegue-cloudflare.md`, arquitectura (nubes e inventario), mapa de dolores (12–15 al día) y README.

## Cómo probar
- `python -m pytest -o addopts="" -p no:cacheprovider -q` → 451 pasan (incluye `workflows/tests/test_cloudflare.py`).
- `node --test edge/estado/test/worker.test.mjs` → 7 pasan.
- En la nube: ver [`docs/despliegue-cloudflare.md`](../despliegue-cloudflare.md), sección "Comprobar que funciona".

## Pendiente
- Crear la cuenta de Cloudflare, hacer `wrangler login` y correr `scripts/cloudflare.sh dev-gabriel` (lo hace el humano: el inicio de sesión es suyo).
- Azure sigue sin secreto en la cuenta de `dev-gabriel` (faltan los datos de Rodrigo).

## Despliegue en `dev-gabriel` (15-nov, noche)
- Worker en `https://telecorp-estado-dev-gabriel.<subdominio>.workers.dev`, KV `telecorp-dev-gabriel-estado`, secreto `telecorp/dev-gabriel/cloudflare` creado por `scripts/cloudflare.sh`.
- **Problema encontrado:** Cloudflare rechazaba las publicaciones con «error code: 1010» (bloquea el User-Agent por defecto de Python, `Python-urllib/…`), así que el disyuntor se abría. Las pruebas no lo veían porque simulan el HTTP.
- **Arreglo:** `nube2/cloudflare.py` envía `User-Agent: telecorp-aws-detector/1.0` en `publicar()` y `sondear()`; la prueba lo exige. Tras redesplegar, el barrido publica (`/salud` con `publicadoEn`).
- Concurrencia reservada sin cambios: 5 Lambdas, 2+1+1+2+1 = 7 (D14).

## Gemini (Google Cloud) activado en `dev-gabriel`
- El secreto `telecorp/dev-gabriel/ia` solo tenía el marcador `PENDIENTE-D2`, así que Gemini no funcionaba aunque el código existía.
- Nuevo `scripts/gemini-secreto.sh <stage>`: pide la clave de Google AI Studio, la comprueba con Google (listar modelos, gratis) y la guarda como `{geminiApiKey, habilitada: true}`, conservando los demás campos. No la imprime (solo enmascarada).
- Verificado: clave válida y `gemini-3.5-flash-lite` responde (HTTP 200).
- Nubes activas en `dev-gabriel`: **AWS + Cloudflare (D15) + Google Gemini**. Azure (D2) sigue en el código pero sin claves en esta cuenta: falta decidir en equipo si queda como opcional.

## Cuatro nubes documentadas (D16)
- Nueva decisión [D16](../decisiones/2026-11-15-cuatro-nubes.md): **AWS + Cloudflare + Google Cloud (Gemini) activas** en `dev-gabriel`; **Azure con código listo pero no desplegada** en la cuenta de la demo (no se pudo activar Azure for Students con la cuenta de Gabriel; la integración se había verificado en `dev-rodrigo` el 14-nov).
- Actualizados D2 (apunta a D16), el índice de decisiones, `arquitectura.md` (cabecera, tablas de nubes y de rúbrica, inventario del secreto `ia`), `README.md` y el diagrama draw.io (Gemini como Google Cloud con flecha continua; Azure «opcional» con flecha punteada).
- **Pendiente:** `docs/arquitectura.svg` (imagen exportada) sigue mostrando la versión AWS + Azure; regenerarla desde el `.drawio`. `AGENTS.md` aún dice «2.ª nube por definir»: cambiarlo requiere OK del equipo (issue `decision`).
