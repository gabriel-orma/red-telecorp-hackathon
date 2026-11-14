---
description: Revisa pedidos de ayuda abiertos y toma uno que no colisione
---

Quiero ayudar a otro miembro del equipo. Sigue AGENTS.md §5, "Ofrecer o tomar ayuda":

1. Sincroniza en versión corta (fetch y ponerse al día con `origin/main`).
2. `gh issue list --label ayuda --state open` y `gh issue list --label en-progreso --state open`.
3. Para cada pedido **sin asignar**, muéstrame en una tabla:
   - n°, título, urgencia (`bloqueado` primero);
   - zona de archivos sugerida;
   - si **choca** con alguna zona `en-progreso` (incluida la mía);
   - el tamaño estimado (S/M/L).
4. Recomiéndame uno, priorizando los que bloquean a alguien y no chocan con nadie.
5. Cuando elija, sigue el flujo de `/tomar` con ese issue: asignar, `en-progreso`, zona de archivos y rama. Comenta en el issue "Lo tomo" con mi plan breve.
6. Al terminar, el PR debe cerrar el issue de ayuda y avisar en el issue original de quien lo pidió.
