# Despliegue de la tercera nube (Cloudflare)

Red TeleCorp publica el estado público de la red en un **Worker de Cloudflare con KV** (decisión [D15](decisiones/2026-11-15-tercera-nube-cloudflare.md)). Si AWS no responde, la página pública usa esa copia, y el Worker sirve además su propia página de estado.

## Qué se crea (plan gratuito, sin tarjeta)
| Recurso | Nombre | Para qué |
|---|---|---|
| Worker | `telecorp-estado-<stage>` (`https://telecorp-estado-<stage>.<tu-subdominio>.workers.dev`) | `PUT /publicar`, `GET /api/estado`, `GET /salud`, `GET /` |
| KV namespace | `telecorp-<stage>-estado` | Última publicación del estado (una clave) |
| Secreto del Worker | `TOKEN_PUBLICACION` | Autoriza a AWS a publicar |
| Secreto en AWS | `telecorp/<stage>/cloudflare` = `{url, token}` | Lo leen el motor `detector` (publica) y el API (panel Nubes) |

## Pasos
1. **Crea la cuenta** en dash.cloudflare.com (gratis).
   - Abre **Workers & Pages** una vez para que se cree tu subdominio `*.workers.dev`.
2. **Inicia sesión** desde Git Bash. Se abre el navegador para autorizar:
   ```bash
   npx wrangler@4.154.0 login
   ```
3. **Despliega el Worker y entrega su URL y su token a AWS.**
   - El script es idempotente y no imprime el token.
   - Necesita credenciales de AWS vigentes.
   ```bash
   bash scripts/cloudflare.sh dev-tualias
   ```
4. **Recompila el frontend** para que la página pública conozca el respaldo:
   ```bash
   bash scripts/deploy.sh dev-tualias frontend
   ```
   Si es la primera vez en el stage o cambió el backend, despliega todo con `bash scripts/deploy.sh dev-tualias`.

## Comprobar que funciona
1. Espera el siguiente barrido del motor (≤ 5 min) y abre `https://telecorp-estado-<stage>.<sub>.workers.dev/`. Debe mostrar el semáforo y "Datos publicados hace …".
2. `GET <url>/salud` → `{"ok": true, "publicadoEn": "…"}`.
3. Panel **Nubes** (operador): "Cloudflare · Operativo".
4. **Prueba de respaldo:** en el navegador, bloquea `*/api/estado` (DevTools → Network → Block request URL) y recarga la página pública. Debe aparecer "copia de respaldo publicada hace X min (Cloudflare)".

## Concurrencia y costos
- **No crea Lambdas:** publica el barrido del motor, que ya existía (D14).
- **Escrituras de KV:** como mucho una cada 4 minutos (≤ 360 al día; el plan gratuito permite 1000).
- **Lecturas de KV:** se guardan 60 s en el borde.
- **Sin cargos:** el Worker no tiene costo dentro del plan gratuito (100 000 pedidos al día).

## Quitarlo
```bash
cd edge/estado && npx wrangler@4.154.0 delete --config wrangler.<stage>.toml
```
```bash
aws secretsmanager delete-secret --secret-id telecorp/<stage>/cloudflare --force-delete-without-recovery
```
