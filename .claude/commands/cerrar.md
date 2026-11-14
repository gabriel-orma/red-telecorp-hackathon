---
description: Documenta la sesión, rebase, push y abre el PR
---

Cierra mi trabajo actual siguiendo AGENTS.md §2, "Al terminar", y §3:

1. **Revisa el diff** (`git diff origin/main...HEAD` y los cambios sin commitear) y verifica:
   - que no haya secretos, `.env`, credenciales ni archivos pesados;
   - que todo esté dentro de mi zona de archivos declarada. Si hay algo fuera, avísame.
2. **Documenta**:
   - Crea `docs/bitacora/AAAA-MM-DD-HHMM-<autor>-<slug>.md` usando `docs/bitacora/_plantilla.md`. El autor es `git config user.name`, en minúsculas y sin espacios. Usa la fecha y hora reales.
   - Actualiza el `README.md` del módulo que toqué (cómo desplegar, probar y usar).
   - Si creé recursos cloud, actualiza el "Inventario" en `docs/arquitectura.md`.
   - Si tomé una decisión técnica, crea `docs/decisiones/AAAA-MM-DD-<slug>.md`.
   - Si cubrí un dolor del cliente, actualiza su estado en `docs/mapa-dolores.md`.
3. Corre las pruebas o la verificación de mi módulo y dime el resultado real.
4. Haz commit, `git fetch origin && git rebase origin/main` (resolviendo conflictos sin perder trabajo ajeno) y `git push -u origin <rama>` (con `--force-with-lease` si ya existía).
5. Crea el PR con `gh pr create`, usando `.github/pull_request_template.md` y `Closes #<n>`.
6. `gh issue edit <n> --remove-label en-progreso` y un comentario con el resumen y el enlace al PR.
7. Dame un resumen final: qué quedó listo, qué quedó pendiente y el enlace al PR.
