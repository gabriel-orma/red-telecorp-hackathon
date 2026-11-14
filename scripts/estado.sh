#!/usr/bin/env bash
# Muestra el estado de sincronización del repo con el equipo.
# Lo ejecuta el hook SessionStart de Claude Code; también se puede correr a mano.
# Es de solo lectura: nunca modifica archivos ni ramas (solo hace `git fetch`).

raiz=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "[estado] No es un repo git."; exit 0; }
cd "$raiz" || exit 0

timeout 15 git fetch origin --prune --quiet 2>/dev/null || echo "[estado] No se pudo hacer git fetch (¿sin red o sin remote?)."

rama=$(git branch --show-current 2>/dev/null)
echo "[estado] Rama actual: ${rama:-desconocida}"

if git rev-parse --verify --quiet origin/main >/dev/null; then
  atras=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
  if [ "$atras" -gt 0 ]; then
    echo "[estado] ⚠ Estás $atras commit(s) ATRASADO respecto de origin/main. Ejecuta /sync antes de editar."
  else
    echo "[estado] Al día con origin/main."
  fi
fi

sucios=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
[ "$sucios" -gt 0 ] && echo "[estado] Hay $sucios archivo(s) con cambios sin commitear."

echo "[estado] Últimas entradas de bitácora en origin/main:"
git ls-tree --name-only origin/main docs/bitacora/ 2>/dev/null | grep -v '_plantilla\|README' | sort | tail -n 5 | sed 's/^/  - /'

if command -v gh >/dev/null 2>&1; then
  echo "[estado] Issues abiertos de coordinación (ayuda / bloqueado / contrato / decision):"
  for l in bloqueado ayuda contrato decision; do
    timeout 15 gh issue list --label "$l" --state open --limit 10 2>/dev/null | sed "s/^/  [$l] /"
  done
else
  echo "[estado] 'gh' no está instalado: revisa los issues en GitHub (ver README)."
fi
exit 0
