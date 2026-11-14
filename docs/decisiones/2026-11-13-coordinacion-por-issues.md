# Coordinación entre agentes por GitHub Issues y documentación en el repo

- Estado: aceptada
- Issue: — (setup inicial)

## Contexto
Tres personas trabajan en paralelo, cada una con su propio agente de IA (Claude Code u otros). Los agentes no comparten memoria ni conversación, así que sin un canal común inventan esquemas distintos y se pisan archivos.

## Decisión
- **Canal de comunicación**: GitHub Issues, con labels (`tarea`, `ayuda`, `contrato`, `decision`, `bloqueado`, `en-progreso`). Cada tarea declara su **zona de archivos**.
- **Memoria compartida**: el repo. Bitácora y decisiones, un archivo por entrada (sin conflictos de merge).
- **Contratos** en `contracts/` como interfaz entre módulos; se cambian solo por un issue `contrato`.
- **Reglas** en `AGENTS.md`, con punteros para cada herramienta (`CLAUDE.md`, `GEMINI.md`, Copilot).

## Consecuencias
- Cada persona necesita `gh` autenticado (o usar la web de GitHub).
- Hay algo de burocracia por tarea, a cambio de no perder tiempo en conflictos ni en integraciones rotas.
