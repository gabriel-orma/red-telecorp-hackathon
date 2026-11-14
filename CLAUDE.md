@AGENTS.md

## Específico de Claude Code

Comandos del proyecto (en `.claude/commands/`):

| Comando | Para qué |
|---|---|
| `/sync` | Traer los últimos cambios y resumir qué hay de nuevo (bitácora, decisiones, issues) |
| `/tomar <issue o descripción>` | Reclamar una tarea: issue, zona de archivos, rama |
| `/ayuda <qué necesitas>` | Abrir un pedido de ayuda para otro agente o persona |
| `/atender` | Ver los pedidos de ayuda abiertos y tomar uno que no colisione |
| `/cerrar` | Documentar (bitácora y READMEs), hacer rebase, push y abrir el PR |

- Al iniciar la sesión, un hook muestra el estado de sincronización (`scripts/estado.sh`). Si dice que estás **atrasado** respecto de `origin/main`, ejecuta `/sync` antes de editar.
- Para tareas de más de un paso, usa el modo plan y valida el plan contra `contracts/` y `docs/arquitectura.md`.
- La memoria de Claude es personal: **lo que el equipo deba saber va al repo** (bitácora, decisiones o issues), no a la memoria.
