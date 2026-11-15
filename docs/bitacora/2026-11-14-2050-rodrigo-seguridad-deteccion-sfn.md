# Seguridad, detección y Step Functions, verificados en AWS

- **Autor**: rodrigo (+ Claude Code)
- **Fecha**: 2026-11-14
- **Issue / PR**: #39
- **Rama**: `fix/seguridad-deteccion-sfn`

## Qué se hizo
- **Seguridad:** grupo Cognito `operadores` + autorizador JWT y comprobación de grupo en el handler para las rutas de operador (incluidas las de E5/E6); identidad = `sub`; vista pública con lista blanca de campos (sin datos personales); entradas del simulador validadas.
- **Detección:** creación del colectivo transaccional e idempotente, fusión atómica de reportes concurrentes, ventana por zona sin depender del GSI, `OTRO` no cuenta como relacionado con el servicio.
- **Step Functions:** `Choice` real sobre la verificación (con antenas sanas no se avisa «falla confirmada»), `Catch`/`Timeout`, monitoreo acotado, avisos por lotes e idempotentes, nombres de estado únicos.
- **Registro de reportes:** reintento rápido ante choques de transacción (antes un reporte podía tardar 3 min por la visibilidad de SQS).
- Se conserva todo E5–E7 de Gabriel (escenarios, recurrencia, analítica, WebSocket, reproducción); la espera de verificación vuelve a **30 s**.

## Archivos y recursos tocados
- Backend: `services/api/src/{acceso,incidencias,colectivos,simulador}.py`, `services/base/layer/python/telecorp/{db,reglas,historial,notificador}.py`, `services/antenas/src/clasificador.py`, `workflows/src/{comun_colectivos,detector,monitoreo,pasos}.py`, `workflows/statemachines/incidente-colectivo.yml`.
- Infra: `services/base/serverless.yml` (grupo `operadores`, alarmas de DLQ, SSM), `services/api/serverless.yml`, `workflows/serverless.yml`.
- Contratos (aditivos): `incidente-colectivo`, `evento-historial`, `reporte`, `usuario`.
- Pruebas nuevas: `services/api/tests/*`, `workflows/tests/*`.

## Cómo probarlo
```bash
pytest services workflows
bash scripts/deploy.sh dev-tualias          # y, tras cada Start Lab: bash scripts/reactivar-lab.sh dev-tualias
```
Alta de un operador: ver `services/api/README.md` («Operadores»).

## Decisiones tomadas
- La recurrencia (E6) se queda tal cual en `main`.
- El comentario libre del operador no se publica en el historial público.

## Pendiente / siguiente paso
- Hallazgos abiertos para Gabriel (en el cuerpo del PR): los datos simulados entran en estadísticas y recurrencia; `REQUIERE_ATENCION` aún no se puede cerrar desde la interfaz.
- No verificado en la nube: restauración PITR, redrive de DLQ, `loggingConfig` y prueba de carga.

## Notas para los otros agentes
- Frontend y backend deben desplegarse juntos (las rutas de operador exigen token).
- `scripts/reactivar-lab.sh` invoca la Lambda de reanudación directamente con credenciales de AWS.
