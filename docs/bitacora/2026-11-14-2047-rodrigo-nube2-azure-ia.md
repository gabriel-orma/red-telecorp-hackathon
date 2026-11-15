# Segunda nube (Azure) e IA con respaldo honesto

- **Autor**: rodrigo (+ Claude Code)
- **Fecha**: 2026-11-14
- **Issue / PR**: #40 (apilado sobre #39)
- **Rama**: `feat/azure-ia-nube2`

## Qué se hizo
- Correo de los avisos por **Azure Communication Services** y clima de la zona por **Azure Maps**, llamados desde Lambdas de AWS (módulo `telecorp.nube2`). Todo con cupos, disyuntor y respaldo: nunca rompe el flujo.
- Análisis del incidente con Gemini **opcional**; sin clave lo genera una plantilla de reglas y la interfaz lo rotula «Reglas (sin IA)» con el motivo. Se regenera durante el monitoreo si cambian afectados o antenas en falla.
- `GET /api/nubes` (solo operadores) y panel «Nubes conectadas»; tarjeta de análisis y chips del canal de aviso en la línea de tiempo.
- Decisión D2 (Azure), diagrama de arquitectura por capas y guía de despliegue de Azure.

## Archivos y recursos tocados
- Nuevo: `services/base/layer/python/telecorp/nube2/*`, `services/api/src/nubes.py`, `frontend/src/{pages/Nubes.tsx,components/neu/TarjetaIA.tsx}`, `docs/{despliegue-azure.md,arquitectura.svg}`, `scripts/azure-secreto.sh`.
- Tocados (mínimo): `notificador.py`, `pasos.py` (`resumir`), `incidencias.py` (triage, apagado por defecto), `LineaTiempo.tsx`, `Colectivos.tsx`, `App.tsx`, `ShellNeu.tsx`.
- Recursos de Azure (fuera de IaC): Maps, Communication Services, Email Service y dominio administrado, todos en ubicación `global`.

## Cómo probarlo
```bash
bash scripts/deploy.sh dev-tualias
bash scripts/azure-secreto.sh dev-tualias <grupo> <comunicacion> <correo> <maps> "tu@correo"   # ver docs/despliegue-azure.md
# con sesión de operador: GET /api/nubes  → azure.acsEmail y azure.maps en OK
pytest services workflows
```

## Decisiones tomadas
- [D2 · Segunda nube: Azure](../decisiones/2026-11-14-segunda-nube-azure.md).
- El texto libre de los usuarios **no** se envía a Gemini (triage apagado: `triageTexto: false`).
- El correo por Azure solo va a la lista `destinatarios` del secreto: las cuentas se auto-verifican (D9).

## Pendiente / siguiente paso
- Probar Gemini real (falta la clave gratuita).
- Un modelo de ML local como alternativa a Gemini (rama aparte).

## Notas para los otros agentes
- Sin claves de Azure el sistema funciona igual (SNS + app, análisis sin clima).
- Verificado en AWS + Azure reales (stage `dev-rodrigo`): flujo completo con 10 usuarios y entrega confirmada por Azure.
