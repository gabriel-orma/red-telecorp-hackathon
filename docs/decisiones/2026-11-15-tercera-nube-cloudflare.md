# D15 · Tercera nube: espejo del estado público en Cloudflare Workers + KV

- **Estado**: ✅ aceptada (pendiente de OK del equipo)
- **Issue**: #48
- **Fecha**: 2026-11-15

## Contexto
- La rúbrica pide "2 nubes o más" (0–3 pts) y valora la alta disponibilidad (0–2 pts). Azure (D2) cumple el mínimo, pero solo para correo y clima.
- La página pública de estado es justo lo que los clientes abren **cuando hay una falla**, y en esa situación se generan más visitas:
  - si AWS cae, la página cae con él;
  - si el API está en su tope de concurrencia (D14), los clientes esperan.
- La tercera nube debía ser **gratuita y sin tarjeta**, y **no agregar Lambdas**, porque AWS Academy desactiva la cuenta con más de 10 a la vez (D14).

## Decisión
**Cloudflare Workers + KV**, en el plan gratuito.

| Pieza | Dónde | Qué hace |
|---|---|---|
| Publicación | AWS: el barrido del motor `detector` (cada 5 min, `workflows/src/detector.py`) | Calcula el estado público, global y por zona (`telecorp/estado_red.py`), y lo envía con `PUT /publicar` y un token. **No hay Lambda nueva.** |
| Worker `telecorp-estado-<stage>` | Cloudflare (`edge/estado/`) | Guarda la publicación en KV y la sirve desde el borde: `GET /api/estado` (mismo contrato que AWS, más el campo `respaldo`), `GET /salud` y `GET /`, una página de estado propia sin dependencias. |
| Respaldo en la página pública | Frontend (`lib/api.ts`) | Pide primero a AWS. Si no responde, usa la copia de Cloudflare y lo dice: "copia de respaldo publicada hace X min". |
| Tablero "Nubes" | `GET /api/nubes` y la página Nubes | Muestra si la última publicación salió bien. Si no hay una reciente, la sonda es `GET /salud`: lee KV, no escribe. |

### Seguridad
- **Token:** el token de publicación vive en AWS Secrets Manager (`telecorp/<stage>/cloudflare` = `{url, token}`) y en el Worker como secreto (`TOKEN_PUBLICACION`). Nunca está en el repo ni se imprime.
- **Validación en el Worker:**
  - compara el token en tiempo constante;
  - valida la forma de la publicación;
  - limita el tamaño a 1 MB;
  - solo acepta `GLOBAL` o `ZONA-nn` como alcance.
- **Sin datos personales:** el estado público no contiene nombres, DNI, GPS ni descripciones. Es lo mismo que ya es público en `/api/estado`.

### Límites del plan gratuito
- **Pedidos:** 100 000 al día. El Worker los atiende sin costo y sin tocar AWS.
- **Escrituras de KV:** 1000 al día. AWS publica como mucho una vez cada 4 minutos, con un cupo atómico en `dedup`, así que hace como máximo 360 escrituras al día (288 con el barrido de 5 min).
- **Lecturas de KV:** se guardan 60 s en el borde (`cacheTtl`), así que hay pocas lecturas aunque haya muchas visitas.

## Alternativas
- **Google BigQuery (sandbox):** histórico y analítica con SQL. Es útil, pero no mejora la disponibilidad y sus tablas expiran a los 60 días.
- **Firebase Firestore:** otra copia de datos sin un rol visible para el cliente.
- **Oracle e IBM Cloud:** piden tarjeta o una verificación lenta.

## Consecuencias
- **Disponibilidad:** el estado de la red sigue visible aunque AWS no responda. Un dato del espejo tiene hasta 5 minutos de antigüedad y la interfaz muestra su edad.
- **Concurrencia (D14):** sin cambios, con 7 Lambdas como máximo. La publicación dura menos de 1 s dentro del barrido que ya existía.
- **Puesta en marcha:** cada persona necesita una cuenta gratuita de Cloudflare.
  1. `npx wrangler@4.154.0 login`, una vez.
  2. `bash scripts/cloudflare.sh <stage>`.
  3. Volver a desplegar el frontend.
  4. Guía completa: [`docs/despliegue-cloudflare.md`](../despliegue-cloudflare.md).
- **Sin el secreto:** la integración queda apagada sin romper nada (el panel la muestra como "Sin configurar").
