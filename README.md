# Red TeleCorp: gestión inteligente de incidencias

Plataforma **serverless y multinube (AWS + segunda nube por definir)** para Red TeleCorp: monitoreo de antenas, portal de incidencias para usuarios, detección de incidentes colectivos, notificaciones, priorización y analítica histórica.

- El reto y la rúbrica: [`docs/reto.md`](docs/reto.md)
- La arquitectura: [`docs/arquitectura.md`](docs/arquitectura.md)
- Avance por dolor del cliente: [`docs/mapa-dolores.md`](docs/mapa-dolores.md)
- **Roadmap por entregas**: [`docs/roadmap.md`](docs/roadmap.md)

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
