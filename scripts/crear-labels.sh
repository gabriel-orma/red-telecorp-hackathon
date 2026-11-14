#!/usr/bin/env bash
# Crea los labels de coordinación en el repo de GitHub (ejecutar una sola vez, requiere `gh auth login`).
set -e
crear() { gh label create "$1" --color "$2" --description "$3" --force; }
crear tarea        "1d76db" "Trabajo a realizar"
crear ayuda        "0e8a16" "Pedido de ayuda para otro agente o persona"
crear contrato     "fbca04" "Cambio propuesto en contracts/"
crear decision     "5319e7" "Decisión técnica a discutir o registrar"
crear bloqueado    "b60205" "Alguien está bloqueado esperando esto"
crear en-progreso  "c5def5" "Reclamado: alguien está trabajando (ver zona de archivos)"
echo "Labels listos."
