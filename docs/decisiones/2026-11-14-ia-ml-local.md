# D12 — IA del triage de reportes: modelo de ML local por defecto, Gemini opcional

- **Fecha:** 2026-11-14 · **Estado:** propuesta verificada, pendiente de OK del equipo
- **Contexto:** la rúbrica pide IA real (3 pts). Gemini exige una clave que no siempre se consigue, envía el texto de los usuarios fuera de AWS y su nivel gratuito puede usar el contenido para mejorar productos de Google.

## Decisión
Los reportes de tipo `OTRO` los clasifica un **modelo de machine learning entrenado por nosotros** (TF-IDF + regresión logística) que corre dentro de la Lambda de registro. Gemini sigue disponible para el análisis del incidente (datos agregados) y, solo si se activa expresamente (`triageTexto: true`), para el triage del texto libre.

## Alternativas
| | ML local | Gemini |
|---|---|---|
| Exactitud | 0,935 medida (prueba a ciegas, datos sintéticos) | no medida (sin clave) |
| Privacidad | el texto no sale de AWS | el texto saldría a Google |
| Latencia / costo | 0,2 ms / 0 | segundos / 0 con cuotas |
| Riesgo | no generaliza a clases nuevas; datos sintéticos | clave, red y cuota |

## Consecuencias
- Un reporte `OTRO` solo suma al conteo de un colectivo si el modelo lo clasifica como falla con confianza ≥ 0,5; la regla de los 10 usuarios sigue siendo determinista para los demás tipos.
- Honestidad: `iaTriage.fuente` es `ML`, `IA` o `REGLAS`; las reglas nunca se presentan como modelo.
- Hay que reentrenar si cambian los tipos de problema. Métricas, protocolo y límites: `ml/triage/README.md`.
