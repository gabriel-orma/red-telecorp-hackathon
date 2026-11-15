# Protecciones económicas de Gemini y procedencia del triage en la interfaz

- **Autor**: rodrigo (+ Claude Code)
- **Fecha**: 2026-11-15
- **Issue / PR**: PR a `main` (continuación de #39, #40 y #42)
- **Rama**: `feat/proteccion-gemini-triage-ui`

## Qué se hizo
- **Gemini solo en el nivel gratuito y apagado por defecto:** hace falta `habilitada: true` en el secreto `ia`; apagarlo surte efecto en la siguiente llamada (el secreto se lee sin caché). La protección principal es que el proyecto de Google no tenga facturación; el código es una red extra.
- Límites por defecto **2 por minuto y 10 al día** (contadores atómicos y persistentes) con topes que la configuración no puede superar; entrada ≤ 4.000 caracteres y salida ≤ 600 tokens.
- Solo modelos con «Free of charge» según la página oficial de precios: `gemini-3.5-flash-lite` y `gemini-3.1-flash-lite`. El valor por defecto anterior (`gemini-2.5-flash-lite`) no pudo verificarse.
- Un 429 abre el disyuntor una hora y nunca se reintenta. En escenarios de demo, con fallas forzadas del simulador o con reportes simulados no se llama a Gemini (`permitirEnSimulacion` solo para grabar la demo).
- Interfaz: el detalle del reporte del operador muestra quién clasificó el texto: **ML local**, **IA generativa** o **Reglas (sin IA)**; la tarjeta de análisis explica el motivo del respaldo.

## Archivos y recursos tocados
`services/base/layer/python/telecorp/nube2/{ia.py,README.md}`, `workflows/src/pasos.py` (detección de simulación), `workflows/tests/test_nube2.py` (15 pruebas nuevas), `frontend/src/{components/neu/TarjetaIA.tsx,pages/PanelIncidencias.tsx,lib/api.ts}`.

## Cómo probarlo
```bash
pytest services workflows
```
En la nube (stage `dev-rodrigo`): regresión E2E y flujo AWS→Azure; el triage de ML dentro de Lambda (ver el PR).

## Decisiones tomadas
- Gemini no se ejecuta si no se puede demostrar que el proyecto de Google no tiene facturación; el modelo de ML local cubre la clasificación y el análisis cae a reglas.

## Pendiente / siguiente paso
- Probar una inferencia real de Gemini cuando se confirme un proyecto sin facturación (una sola solicitud controlada).

## Notas para los otros agentes
- Esto estaba en la rama del #42 pero se subió justo después de que se integrara #43; este PR lo lleva a `main`.
