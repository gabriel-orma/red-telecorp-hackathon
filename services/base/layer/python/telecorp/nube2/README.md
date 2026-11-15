# `telecorp.nube2` — segunda nube (Azure) e IA opcional

Integraciones **de AWS hacia otras nubes**, todas con `urllib` (sin dependencias nuevas) y con una regla común: **nunca rompen el flujo del negocio**. Si una integración falla, el flujo sigue con un respaldo y el motivo queda visible.

| Módulo | Qué hace | Respaldo si falla |
|---|---|---|
| `azure_acs.py` | Correo transaccional por **Azure Communication Services** (REST `emails:send`, firma HMAC-SHA256) | SNS (suscripción confirmada) y aviso en la app |
| `azure_maps.py` | **Azure Maps**: clima actual del centro de la zona (`weather/currentConditions`) | El análisis se genera sin clima |
| `ia.py` | **Gemini** (API REST, nivel gratuito): análisis del incidente sobre datos **agregados** | Plantilla determinista (`fuente: "REGLAS"`), rotulada «sin IA» en la interfaz |
| `estado.py` | Cupos atómicos por minuto/hora, disyuntor y tablero de salud (todo en la tabla `dedup`, sin recursos nuevos) | — |
| `secretos.py` | Lee los secretos de AWS Secrets Manager con caché corta | La integración queda «no configurada» |

## Secretos (AWS Secrets Manager, nunca en el repo)
- `telecorp/<stage>/azure` → `{acsEndpoint, acsKey, acsSender, mapsKey, destinatarios}`
  - `destinatarios`: **lista autorizada** de correos exactos o dominios (`"@utec.edu.pe"`). Sin lista no se envía nada: las cuentas se auto-verifican en Cognito (D9) y, sin esta barrera, cualquiera podría hacer que el remitente escriba a un tercero.
  - Opcional: `limiteHora` (por defecto 8; el dominio administrado de Azure admite 10/h y 5/min).
- `telecorp/<stage>/ia` → `{geminiApiKey, habilitada, modelo, limiteMinuto, limiteHora, limiteDia, triageTexto, permitirEnSimulacion}`
  - **Seguridad económica (Gemini solo en el nivel gratuito):** la protección principal es que el proyecto de Google **no tenga facturación** (sin cuenta de facturación no existe el nivel de pago). Los límites del código son una red adicional, no una garantía frente a una clave comprometida.
  - `habilitada`: **apagado por defecto**; Gemini solo se llama con `habilitada: true`. Poner `false` lo desactiva en la siguiente llamada (el secreto se lee sin caché), sin desplegar.
  - `modelo`: solo `gemini-3.5-flash-lite` o `gemini-3.1-flash-lite` (modelos con «Free of charge» en la página oficial de precios, verificada el 14-nov-2026); cualquier otro se rechaza.
  - Límites por defecto: **2 por minuto y 10 al día** para todo el proyecto (contadores atómicos y persistentes); la configuración puede bajarlos, nunca superar los topes (5/min, 30/h, 50/día). Entrada ≤ 4.000 caracteres y salida ≤ 600 tokens.
  - Un **429** abre el disyuntor una hora y **nunca se reintenta**; otros errores abren el disyuntor tras 3 fallos seguidos (5 min). Con cualquier límite alcanzado se usa el análisis de reglas y el motivo queda registrado (`motivoFallback`).
  - `permitirEnSimulacion` (por defecto no): durante un escenario de demo, con fallas forzadas en el simulador o con reportes simulados **no se llama a Gemini**, para no gastar la cuota en datos simulados. Se activa solo para grabar la demo con IA real.
  - `triageTexto` (por defecto **apagado**): si es `true`, el texto libre de un reporte `OTRO` se enmascara y se envía a Gemini. Apagado, la IA solo recibe agregados. El nivel gratuito puede usar el contenido para mejorar los productos de Google; las máscaras de datos personales reducen el riesgo, no lo eliminan.

Recursos de Azure (creados con `az` en ubicación `global`, sin IaC en este repo): una cuenta de **Azure Maps** (SKU Gen2) y una de **Communication Services** con su *Email Communication Service* y un dominio administrado por Azure (`DoNotReply@<dominio>.azurecomm.net`). Las claves se copian a Secrets Manager (arriba). La suscripción de estudiante (UTEC) solo permite recursos de ubicación **`global`** (política «Allowed locations»), que bastan para ACS y Maps. **No se intenta eludir esa política.**

## Qué NO hace la IA
No decide umbrales de antena, la regla de los 10 usuarios ni la prioridad: eso es código determinista con pruebas. La IA solo redacta hipótesis y recomendaciones para el operador, y la salida se valida contra un esquema cerrado (`enum`, longitudes, rangos).

## Pruebas
- Unitarias y de integración interna (sin red): `pytest services/base/tests/test_nube2_*.py workflows/tests/test_nube2.py services/api/tests/test_nubes.py`.
- **En la nube real:** `GET /api/nubes` (solo operadores) mide Azure y AWS con operaciones reales; el flujo completo (10 usuarios → Step Functions → clima → correo) se prueba con un destinatario autorizado.
- Hallazgo medido (14-nov-2026): consultar en ACS una operación inexistente tarda ~30 s y responde 504; la sonda de estado usa `emails:send` con destinatarios vacíos (400 con clave válida, 401 con clave mala; no envía nada).
