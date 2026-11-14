---
description: Trae los últimos cambios y resume qué hay de nuevo en el equipo
---

Sincroniza este repo con el equipo siguiendo AGENTS.md §2:

1. Ejecuta `git fetch origin --prune` y `git status`.
   - Si hay cambios sin commitear, **no los pierdas**: avísame y pregunta si hacer commit o `git stash` antes de seguir.
   - Si estás en `main`: `git pull --rebase origin main`.
   - Si estás en una rama de trabajo: `git rebase origin/main`. Si hay conflictos, resuélvelos conservando el trabajo de ambos lados. Si el conflicto está en una zona de otra persona, detente y avísame.
2. Lista los archivos de `docs/bitacora/` y `docs/decisiones/` que cambiaron desde mi última sincronización (`git log --since="2 days ago" --name-only -- docs/` o según el historial), y **léelos**.
3. Si existe `gh`, ejecuta `gh issue list --state open --limit 50` y destaca:
   - issues con los labels `ayuda`, `contrato`, `decision` o `bloqueado`;
   - issues `en-progreso` y su **zona de archivos** declarada.
4. Si cambió algo en `contracts/` o en `AGENTS.md`, léelo completo.

Termina con un resumen corto en español:
- **Novedades**: qué hicieron los demás (de la bitácora).
- **Decisiones y contratos**: qué cambió.
- **Coordinación**: pedidos de ayuda abiertos y zonas ocupadas.
- **Mi estado**: rama actual, si estoy al día y qué tengo pendiente.
