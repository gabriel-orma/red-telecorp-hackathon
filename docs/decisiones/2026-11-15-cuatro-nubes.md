# D16 — Nubes de la solución: AWS + Cloudflare + Google Cloud (Gemini) + Azure

- **Fecha:** 2026-11-15 · **Estado:** aceptada (pendiente de OK del equipo, issue `decision`)
- **Actualiza:** [D2](2026-11-14-segunda-nube-azure.md) (Azure como 2.ª nube) y [D15](2026-11-15-tercera-nube-cloudflare.md) (Cloudflare).

## Contexto
- La rúbrica pide **2 nubes o más** (Vercel no cuenta).
- El código integra **cuatro proveedores**, pero no todos quedaron activos en la cuenta de AWS de la demo, que es la última cuenta del Learner Lab: stage `dev-gabriel`, cuenta 155735997418.
- **Azure:** Rodrigo la verificó el 14-nov en su stage `dev-rodrigo`, con su suscripción Azure for Students. El 15-nov, en la cuenta de la demo, no se pudieron crear recursos propios: no se pudo activar Azure for Students con la cuenta de Gabriel, y el inicio de sesión de `az` no encontró una suscripción utilizable.
- **Gemini:** D2 decía que «Gemini no cuenta como nube» porque es una API de IA. Ahora la clave sale de Google AI Studio, y **cada clave de AI Studio pertenece a un proyecto de Google Cloud**. El servicio es la Gemini API de Google Cloud, consumida desde las Lambdas.

## Decisión
La solución es **multinube con cuatro proveedores**. Este es el estado real en la cuenta de la demo:

| # | Nube | Servicios | Rol | Estado en `dev-gabriel` |
|---|---|---|---|---|
| 1 | **AWS** | API Gateway, Lambda, SQS, DynamoDB, Step Functions, Cognito, EventBridge, Secrets Manager, SSM, S3 | Plataforma principal | ✅ Desplegada (D14: tope de 7 Lambdas a la vez) |
| 2 | **Cloudflare** | Workers + KV | Alta disponibilidad: espejo del estado público, sigue en línea aunque AWS caiga | ✅ Desplegada; publica cada 5 min ([D15](2026-11-15-tercera-nube-cloudflare.md)) |
| 3 | **Google Cloud** | Gemini API (`gemini-3.5-flash-lite`) | IA generativa: hipótesis y recomendaciones del incidente con datos agregados | ✅ Activa; clave verificada el 15-nov (`scripts/gemini-secreto.sh`) |
| 4 | **Microsoft Azure** | Communication Services (correo) + Maps (clima) | Avisos por correo y clima de la zona | ⚠️ Código listo y verificado en `dev-rodrigo` el 14-nov; **no desplegada en la cuenta de la demo** |

- **Azure queda opcional.** Sin su secreto (`telecorp/<stage>/azure`) el sistema funciona igual:
  - los avisos salen por la app y por SNS;
  - el análisis del incidente se hace sin clima.

  El panel **Nubes** lo muestra como «No configurada», nunca como caída.
- **Para activarla** en cualquier stage, basta con una suscripción de Azure que permita recursos `global`: seguir [`despliegue-azure.md`](../despliegue-azure.md) y ejecutar `scripts/azure-secreto.sh`. No hace falta redesplegar.
- **Las dos más fáciles de defender son AWS y Cloudflare.** En las dos se despliega cómputo y almacenamiento propios. Google Cloud se usa como servicio consumido (API).

## Consecuencias
- **Rúbrica:** cumple «2 o más nubes» solo con lo desplegado (AWS + Cloudflare), y Google suma una tercera activa. Azure muestra que la arquitectura admite un cuarto proveedor sin cambiar el código.
- **Concurrencia (D14):** ninguna nube agrega Lambdas.
  - Cloudflare publica desde el barrido que ya existía.
  - Gemini y Azure se llaman desde Lambdas existentes, con topes y cupos.
- **Costo:** todo está en planes gratuitos.
  - Cloudflare: Workers y KV gratis, ≤ 360 escrituras al día.
  - Gemini: nivel gratuito, con límites de llamadas en el secreto.
  - Azure: dominio de correo administrado y Maps Gen2, pago por uso.
- **Privacidad:** a Gemini solo se envían datos agregados, nunca el texto libre de los usuarios (D12).
- **Secretos:** las claves de las tres nubes externas viven solo en Secrets Manager:
  - `telecorp/<stage>/cloudflare`;
  - `telecorp/<stage>/ia`;
  - `telecorp/<stage>/azure`.
