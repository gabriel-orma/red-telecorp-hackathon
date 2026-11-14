# D2 — Segunda nube: Microsoft Azure (Communication Services + Maps)

- **Fecha:** 2026-11-14 · **Estado:** propuesta verificada, pendiente de OK del equipo (issue `decision`)
- **Sustituye a:** la propuesta inicial de GCP (BigQuery + Gemini).

## Contexto
La rúbrica pide **2 nubes o más**. Se probó, con comandos reales, qué permite cada una:

| Opción | Resultado verificado |
|---|---|
| Azure regional (Functions, Storage, OpenAI, Language…) | **Denegado.** La política integrada «Allowed locations», asignada por la universidad en un grupo de administración que el alumno no puede leer ni modificar, solo admite `qatarcentral`; además la política de Students limita a 5 regiones. No se intentó eludirla. |
| Azure con ubicación `global` | **Permitido.** Se crearon Azure Maps (Gen2) y Communication Services con dominio de correo administrado. |
| GCP (BigQuery sandbox + Gemini) | No se llegó a probar: requería un inicio de sesión de Google y no aportaba más que lo anterior para la rúbrica. |
| Bedrock / SES / SNS-SMS en AWS | Denegados desde `LabRole` en el Learner Lab. |

## Decisión
La segunda nube es **Azure**, con dos servicios que cumplen una función de negocio real:

1. **Communication Services (correo):** AWS Step Functions → Lambda `notificar` → ACS. Reemplaza al correo que SES no permite en el Learner Lab. Se envía solo a quien aceptó avisos por correo, nunca a reportes simulados ni dominios reservados.
2. **Maps (clima):** el análisis del incidente incluye el clima actual de la zona.

**Gemini no cuenta como nube**: es una API de IA. Si no hay clave, el análisis lo produce una plantilla determinista y la interfaz lo etiqueta «Reglas».

## Consecuencias
- Las claves de Azure viven en AWS Secrets Manager (`telecorp/<stage>/azure`); nunca en el repo.
- Costo: dentro de la cuota gratuita / crédito de estudiante; el código limita 5 correos/min y 8/h y cachea el clima 10 min por zona.
- Riesgo asumido: el dominio de correo administrado de Azure puede mandar a spam; el límite horario es bajo (suficiente para la demo).
