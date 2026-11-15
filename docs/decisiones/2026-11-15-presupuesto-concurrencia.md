# D14 · Presupuesto de concurrencia: máximo 7 Lambdas a la vez

- **Estado**: ✅ aceptada
- **Fecha**: 2026-11-15
- **Contexto**: dos cuentas de AWS Academy se desactivaron solas.

## Problema
El README del Learner Lab dice: *"A maximum of 10 concurrent running Lambda execution environment instances are permitted"* y *"Any attempt to exceed a service limit, may result in immediate deactivation of the AWS account"*. AWS mantiene su límite normal (1000), así que **nada frena a la app**: el control lo hace Vocareum por fuera, desactivando la cuenta.

La arquitectura anterior tenía 54 Lambdas y varias formas de multiplicarlas: una por ruta del API (una pantalla = 5 Lambdas), la Lambda `web` (abrir la app = ~12), colas SQS sin tope, `Map ×5` por incidente, el simulador durmiendo dentro de la Lambda. Pico estimado en la simulación acelerada: 35–50.

## Decisión
Cada función tiene **`reservedConcurrency`** (tope duro de AWS: no puede haber más copias ejecutándose) y la **suma de todos los topes es 7**. Quedan 3 de margen para las 5 Lambdas propias del laboratorio (`MainMonitoringFunction`, `ModLabRole`, etc.), que no podemos ver ni controlar.

| Función | Atiende | Tope |
|---|---|---|
| `telecorp-<stage>-api` | Router único: 26 rutas HTTP + WebSocket (`src/router.py`) | 2 |
| `telecorp-<stage>-segundo-plano` | SQS reportes + 3 DynamoDB Streams (avisos en vivo) | 1 |
| `telecorp-<stage>-simulador` | Simulador (Scheduler) + clasificador (SQS métricas) | 1 |
| `telecorp-<stage>-detector` | Motor: streams del detector, barrido cada 5 min y los 17 pasos de las 3 Step Functions (`src/motor.py`) | 2 |
| `telecorp-<stage>-pre-registro` | Trigger de Cognito | 1 |
| **Total** | | **7** |

Cambios que acompañan los topes (para que "ocupado" signifique **esperar**, nunca perder datos):
- **Frontend sin Lambda**: el HTTP API entrega `index.html` y `/assets/*` directo desde S3 (integración `HTTP_PROXY`, bucket de solo lectura pública). `scripts/publicar-frontend.py` fija tipo, caché y gzip.
- **Step Functions**: toda tarea llama al motor con `"accion"`; el primer reintento de cada tarea es `Lambda.TooManyRequestsException` (hasta 40 intentos con espera creciente). Los `Map` avanzan de a uno.
- **Colas**: visibilidad 60 s y `maxReceiveCount` 20 (un rechazo por "ocupado" cuenta como recepción). AWS no permite `maximumConcurrency` > tope de la función.
- **Simulador**: ya no duerme entre lecturas; encola las 4 muestras del minuto con `DelaySeconds` (0/15/30/45 s) y termina en menos de 1 s.
- **Navegador**: máximo 2 pedidos al API en vuelo (`lib/limitador.ts`) y reintento con espera ante 429/5xx de "ocupado".
- **Simulación acelerada**: monitoreo cada 8 s (antes 4 s).

## Garantía
`services/api/tests/test_presupuesto_concurrencia.py` falla si una función no tiene tope, si la suma pasa de 7, si una Step Function llama a otra Lambda o si un reintento no espera al motor. **Antes de agregar una función, hay que quitarle cupo a otra.**

## Reglas de uso para no bloquear la cuenta
Los topes protegen lo que se despliega **desde este código**. El riesgo que queda está fuera de él:

1. **Despliega solo con `bash scripts/deploy.sh`**, desde una rama que incluya D14. Antes de desplegar, el script corre las pruebas del presupuesto y **se detiene si fallan**. Una versión vieja (54 Lambdas sin topes) desplegada en la cuenta vuelve a exponerla al bloqueo.
2. **No crees Lambdas a mano** en la consola y no pruebes otros proyectos en la misma cuenta: todas comparten el límite de 10.
3. **Nueva función = quitar cupo a otra.** Si agregas una función, ponle `reservedConcurrency` y baja el de otra para que la suma siga siendo ≤ 7 (la prueba lo exige).
4. **Nada de `maximumConcurrency` en SQS mayor que el tope de la función** (AWS rechaza el despliegue).
5. **Step Functions**: toda tarea nueva llama al motor `detector` con una `"accion"` registrada en `workflows/src/motor.py` (`PASOS`), con el reintento de `Lambda.TooManyRequestsException` primero y `Map` con `MaxConcurrency: 1`.
6. **Prueba de carga** (`scripts/demo/carga.py`): solo con valores bajos. No supera el tope, pero la cola tardaría mucho en vaciarse.
7. **Apaga el simulador** cuando no lo uses (desde el panel; tras cada despliegue queda apagado por defecto).
8. **Verifica** después de una demo: CloudWatch → `AWS/Lambda` → `ConcurrentExecutions` (máximo, periodo 1 min) debe quedar ≤ 7. En la verificación del 2026-11-15 el máximo fue 6.

Los errores 503 que aparecen en la consola del navegador durante un pico son rechazos por "ocupado" que `lib/limitador.ts` reintenta solo: son esperados.

## Costo de la decisión
- Picos más lentos (los reportes y pasos esperan su turno), sin pérdida de datos.
- Si dos operadores cargan muchas pantallas a la vez, alguna respuesta tarda 1–2 s más (reintento del navegador).
- El frontend pierde la caché en memoria de la Lambda `web`; la compensa la caché del navegador (assets inmutables) y gzip.

## Verificación
Métrica de CloudWatch `AWS/Lambda ConcurrentExecutions` (máximo de la cuenta) durante la simulación acelerada: ver bitácora de esta fecha.
