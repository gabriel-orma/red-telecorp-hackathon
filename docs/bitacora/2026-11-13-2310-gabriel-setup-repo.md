# Setup inicial del repo y reglas para agentes

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-13 23:10
- **Issue / PR**: — (commit inicial)
- **Rama**: main

## Qué se hizo
- Se creó la estructura del repo y las reglas para los agentes (`AGENTS.md`, con punteros `CLAUDE.md`, `GEMINI.md` y `.github/copilot-instructions.md`).
- Se definió la coordinación entre agentes por GitHub Issues (labels `tarea`, `ayuda`, `contrato`, `decision`, `bloqueado`, `en-progreso`) con plantillas.
- Se agregaron los comandos de Claude Code `/sync`, `/tomar`, `/ayuda`, `/atender` y `/cerrar`, y un hook de inicio (`scripts/estado.sh`) que avisa si estás atrasado respecto de `main`.
- Se documentaron el reto, la arquitectura propuesta, el mapa de dolores y los contratos v0 (borrador).

## Archivos y recursos tocados
- Todo el repo (commit inicial). No se crearon recursos cloud.

## Cómo probarlo
```bash
bash scripts/estado.sh
```

## Decisiones tomadas
- [2026-11-13-coordinacion-por-issues](../decisiones/2026-11-13-coordinacion-por-issues.md)

## Pendiente / siguiente paso
- Resolver las decisiones abiertas de `docs/decisiones/README.md` (cuentas AWS, IaC, runtime, frontend, región).
- Revisar y aprobar los contratos v0 en `contracts/`.

## Notas para los otros agentes
- Los contratos están en **borrador v0**: se pueden ajustar con un issue `contrato` antes de que alguien construya sobre ellos.
