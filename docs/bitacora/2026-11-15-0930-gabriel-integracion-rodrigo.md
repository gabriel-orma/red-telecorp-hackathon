# Integración: seguridad, Azure + IA y ML de Rodrigo sobre la línea de tiempo

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-15 09:30
- **PR**: integra #39, #40 y #42 (de rodrigoanco-debug) sobre #41
- **Rama**: feat/integracion-rodrigo-linea-tiempo

## Qué se hizo
- Se fusionó la rama de #42 (que contiene #39 y #40) sobre `main`, que ya tenía la línea de tiempo (#41).
- Conflictos resueltos conservando ambos lados:
  - `workflows/src/comun_colectivos.py`: se queda la creación **transaccional** de Rodrigo. La simulación acelerada se reubicó: `factorTiempo` en `_colectivo_nuevo()` y el monitoreo de 4 s en `asegurar_ejecucion()` (decide por `factorTiempo`, sin otra lectura de SSM).
  - `services/api/serverless.yml`: rutas de ambos; `/api/linea-tiempo` ahora lleva autorizador.
  - `PanelIncidencias.tsx` (vista de operador + polling adaptativo), `ShellNeu.tsx` (Línea de tiempo + Nubes conectadas), `lib/api.ts` (ambos bloques).
- **Línea de tiempo solo para operadores** (`@acceso.solo_operadores`): devuelve el punto GPS de cada reporte. La página muestra un aviso con enlace al ingreso si no hay sesión de operador, y oculta "Simular escenario".
- `scripts/crear-operador.sh <stage> <correo>`: crea el operador de la demo (contraseña en `scripts/demo/.operador-<stage>.local`, ignorado por git).
- Pruebas: 366 en verde (incluye las de Rodrigo con `moto`).

## Pendiente
- Recursos de Azure sin IaC (creados con `az`): en una cuenta AWS nueva hay que volver a cargar el secreto con `scripts/azure-secreto.sh`; sin él, los avisos van por SNS/app y el análisis usa reglas.
- Hallazgos abiertos de #39 (datos simulados en la analítica, `REQUIERE_ATENCION` sin cierre desde la UI, etc.).
