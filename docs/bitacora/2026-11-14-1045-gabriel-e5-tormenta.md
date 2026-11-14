# E5: Simulación de tormenta + resiliencia + prueba de carga

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 10:45
- **Issue / PR**: #30
- **Rama**: feat/30-e5-tormenta

## Qué se hizo
- **Roadmap reordenado** (decisión del equipo): E4 (2.ª nube + IA) pasa al final; primero E5–E8 en AWS.
- **Step Function `escenario`**: tormenta (zona + vecinas) o corte de energía (zona) en oleadas, con Map secuencial y Wait. Los reportes de vecinos ficticios siguen el mismo camino que los reales. Planificador puro en `telecorp.escenarios`, con 3 pruebas.
- **API**: lanzar, consultar y **Reiniciar demo** (quita fallas, restablece y reanuda incidentes).
- **Frontend**: botón "Simular escenario" (tormenta o corte, con selector de zona), progreso de oleadas con barra degradada, botón de reinicio y **onda de propagación** de ~900 m desde cada antena caída (ease-out, visible a cualquier zoom).
- **Resiliencia del Learner Lab** (encontrado al probar):
  - al detenerse la sesión, AWS desactiva las conexiones SQS → Lambda y las Step Functions en curso fallan;
  - `scripts/reactivar-lab.sh` reactiva las colas y reanuda los incidentes huérfanos (nuevo modo `reanudar` de la Step Function); `deploy.sh` lo ejecuta siempre.
- **Prueba de carga** `scripts/demo/carga.py`.

## Resultados en el lab
| Prueba | Resultado |
|---|---|
| Tormenta en Miraflores | 5 oleadas, 27 reportes, 15 antenas → colectivo en Miraflores (22 afectados) + proactivos en vecinas ✅ |
| Corte de energía en Hospital Rebagliati (desde la UI) | 4 oleadas, 3 antenas apagadas, alerta Sonner y colectivo proactivo ✅ |
| Reiniciar demo | 12 incidentes cerrados en ~30 s, antenas normales ✅ |
| Carga: 480 reportes (40 usuarios × 12 zonas, concurrencia 40) | 480/480 aceptados en 5,5 s (88/s), 480/480 registrados, **0 perdidos, DLQ vacía** ✅ |
| Incidente huérfano tras apagar el lab | Reanudado automáticamente al desplegar ✅ |

## Pendiente / siguiente paso
- E6: inteligencia operativa.
- Los 480 reportes de la prueba de carga quedan en las estadísticas de 24 h de `dev-gabriel`: el mapa de calor se verá "caliente" hasta mañana.

## Notas para los otros agentes
- **Tras cada Start Lab: `bash scripts/reactivar-lab.sh dev-<alias>`.** Si no, nada se procesa (las colas acumulan mensajes).
- La API construye los ARN de las Step Functions por nombre (`telecorp-<stage>-…`) porque el stack `api` se despliega antes que `workflows`.
- Imports entre módulos de `services/api/src/` dentro de una Lambda: `from src.<modulo> import …` (el handler se carga como `src.<modulo>`).
