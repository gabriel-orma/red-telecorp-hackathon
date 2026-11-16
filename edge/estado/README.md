# Espejo del estado público (Cloudflare Workers + KV)

Tercera nube de Red TeleCorp ([D15](../../docs/decisiones/2026-11-15-tercera-nube-cloudflare.md)). AWS publica aquí el estado público cada 5 minutos, y este Worker lo sirve desde el borde aunque AWS no responda.

| Ruta | Qué hace |
|---|---|
| `PUT /publicar` | Solo AWS (`Authorization: Bearer <TOKEN_PUBLICACION>`): guarda la publicación en KV |
| `GET /api/estado?zonaId=` | Mismo contrato que `GET /api/estado` de AWS, más `respaldo: {fuente, publicadoEn, edadS}` (CORS abierto) |
| `GET /salud` | Sonda del panel Nubes: lee KV, no escribe |
| `GET /` | Página de estado propia (`src/pagina.js`, sin dependencias) |

- **Código:** `src/index.js` (rutas y validación) y `src/pagina.js` (HTML).
- **Pruebas:** con un KV en memoria.
  ```bash
  node --test test/worker.test.mjs
  ```
- **Despliegue:** `bash scripts/cloudflare.sh <stage>`, que genera `wrangler.<stage>.toml` desde `wrangler.plantilla.toml` con el id del KV de tu cuenta. Ese archivo está en `.gitignore`.
- **Guía completa:** [`docs/despliegue-cloudflare.md`](../../docs/despliegue-cloudflare.md).
