# Red TeleCorp: gestión inteligente de incidencias

Plataforma **serverless y multinube**: AWS, Cloudflare, Google Cloud (Gemini) y Azure ([D16](docs/decisiones/2026-11-15-cuatro-nubes.md)). En la demo están activas las tres primeras; Azure tiene el código listo, pero no se pudo desplegar en la cuenta de la demo. para Red TeleCorp: monitoreo de antenas, portal de incidencias para usuarios, detección de incidentes colectivos, notificaciones, priorización y analítica histórica.

- El reto y la rúbrica: [`docs/reto.md`](docs/reto.md)
- La arquitectura: [`docs/arquitectura.md`](docs/arquitectura.md)
- Avance por dolor del cliente: [`docs/mapa-dolores.md`](docs/mapa-dolores.md)
- **Roadmap por entregas**: [`docs/roadmap.md`](docs/roadmap.md)

## Despliegue (replicable en cualquier cuenta)

Requisitos: Node 20+, Python 3.12, AWS CLI v2 y **Git Bash** en Windows. Las credenciales del Learner Lab (*AWS Details*) van en `~/.aws/credentials`.

Instala las dependencias (Serverless Framework v3 queda fijado en el repo):
```bash
npm ci
```

Despliega todo: base → antenas → api → workflows → frontend. La primera vez tarda unos 8 minutos.
```bash
bash scripts/deploy.sh dev-tualias
```

> ⚠️ **AWS Academy desactiva la cuenta si hay más de 10 Lambdas ejecutándose a la vez.** Toda la app está limitada a 7 (decisión [D14](docs/decisiones/2026-11-15-presupuesto-concurrencia.md)) y `deploy.sh` se detiene si las pruebas del presupuesto fallan. No despliegues versiones viejas ni crees Lambdas a mano en la cuenta: lee las reglas de uso en D14.

Al terminar imprime la URL HTTPS del centro de control. Para desplegar solo una parte: `bash scripts/deploy.sh dev-tualias frontend` (o `api`, `antenas`, `base`).

**Tercera nube (Cloudflare):** el estado público se publica cada 5 min en un Worker de Cloudflare, que lo sigue sirviendo aunque AWS caiga. Es opcional y gratis; ver [`docs/despliegue-cloudflare.md`](docs/despliegue-cloudflare.md) (`npx wrangler@4.154.0 login` y luego `bash scripts/cloudflare.sh dev-tualias`).

**IA en Google Cloud (Gemini):** clave gratis en https://aistudio.google.com/apikey (cualquier cuenta de Google, sin tarjeta); se valida y se guarda en Secrets Manager con `bash scripts/gemini-secreto.sh dev-tualias`.

**Azure (opcional, no desplegada en la demo):** el correo de los avisos y el clima de la zona salen por Azure. Sin sus claves el sistema funciona igual (avisos por la app y SNS, análisis sin clima), pero para la demo completa crea los recursos y entrega sus claves a Secrets Manager siguiendo [`docs/despliegue-azure.md`](docs/despliegue-azure.md).

Elimina todo cuando no lo uses, para no gastar el presupuesto del lab:
```bash
bash scripts/remove.sh dev-tualias
```

Datos de demo: 8 días de historial para la línea base (una sola vez por stage) y reportes con cuentas demo de Cognito:
```bash
python scripts/demo/historico.py dev-tualias
```
```bash
python scripts/demo/reportar.py https://<id>.execute-api.us-east-1.amazonaws.com --zona ZONA-05 --n 12
```

Después de cada Start Lab del Learner Lab (AWS desactiva las colas al detener la sesión):
```bash
bash scripts/reactivar-lab.sh dev-tualias
```

Prueba de carga (cientos de reportes por el camino real; verifica 0 pérdidas y DLQ vacía):
```bash
python scripts/demo/carga.py https://<id>.execute-api.us-east-1.amazonaws.com --stage dev-tualias
```

Pruebas unitarias:
```bash
python -m pytest
```

| Stack | Qué contiene |
|---|---|
| [`services/base`](services/base) | Tablas DynamoDB (PITR), colas SQS + DLQ, SSM, Secrets Manager, layer Python común |
| [`services/antenas`](services/antenas) | Simulador (EventBridge Scheduler) y clasificador de métricas |
| [`services/api`](services/api) | HTTP API: datos en `/api/*` y frontend por HTTPS en `/` |
| [`workflows`](workflows) | Detector de incidentes colectivos (Streams) y Step Function del ciclo de vida |
| [`frontend`](frontend) | Centro de control (React + MapLibre) |

## Cómo trabajamos (3 personas, cada una con su agente de IA)

**Lee [`AGENTS.md`](AGENTS.md) antes de empezar.** En resumen:

1. **Siempre al día**: `git pull --rebase` antes de editar. En Claude Code, `/sync`.
2. **Toda tarea tiene un issue** con su **zona de archivos**, y nadie edita la zona de otro. En Claude Code, `/tomar`.
3. **Los agentes se comunican por GitHub Issues**: pedidos de ayuda (`/ayuda`), tomar pedidos (`/atender`), cambios de contrato y decisiones.
4. **Todo queda documentado**: bitácora por sesión, decisiones, README por módulo. En Claude Code, `/cerrar`.
5. **Contratos** (`contracts/`) como interfaz entre módulos: se trabaja con mocks y no se espera a nadie.

## Primeros pasos para cada integrante

```bash
git clone <url-del-repo> && cd <repo>
```

1. Instala [GitHub CLI](https://cli.github.com/) y autentícate: `gh auth login`.
2. Configura tu nombre en git (se usa en la bitácora): `git config user.name "<tu-alias>"`.
3. Copia `.env.example` a `.env` y completa tus valores locales (nunca se suben al repo).
4. Abre el repo con tu agente:
   - **Claude Code**: lee `CLAUDE.md` automáticamente; al iniciar verás el estado de sincronización.
   - **Codex / Cursor**: leen `AGENTS.md`.
   - **Gemini CLI**: lee `GEMINI.md`, que apunta a `AGENTS.md`.
   - **Un chatbot web** (ChatGPT, Gemini, Claude.ai): pégale `AGENTS.md` y `docs/arquitectura.md` al inicio.
5. Revisa las decisiones abiertas en [`docs/decisiones/README.md`](docs/decisiones/README.md).

## Entregables (Canvas)
- Video pitch de **5 minutos como máximo**.
- Este repositorio.
- El diagrama de arquitectura.
- **No se entrega informe**: anula la participación.
