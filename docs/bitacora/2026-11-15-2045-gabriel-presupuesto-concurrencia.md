# Presupuesto de concurrencia (D14) y despliegue en la cuenta nueva

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-15 20:45
- **Rama**: feat/presupuesto-concurrencia (sobre la integración de la fase final de Rodrigo y el Inicio)
- **Cuenta**: AWS Academy 155735997418, stage `dev-gabriel` → https://l02w04wek6.execute-api.us-east-1.amazonaws.com

## Por qué
Dos cuentas de AWS Academy se desactivaron. El README del Learner Lab permite **10 Lambdas ejecutándose a la vez** y desactiva la cuenta al superarlo. La arquitectura anterior (54 Lambdas sin tope) llegaba a 35–50 en la simulación acelerada.

## Qué se hizo
Ver la decisión [D14](../decisiones/2026-11-15-presupuesto-concurrencia.md). En resumen: 5 Lambdas con `reservedConcurrency` (api 2, segundo-plano 1, simulador 1, detector 2, pre-registro 1 = **7**), frontend servido desde S3 sin Lambda, Step Functions que esperan si el motor está ocupado, simulador sin dormir, navegador con máximo 2 pedidos en vuelo. Pruebas que fallan si una función no tiene tope o la suma supera 7.

Corrección encontrada en la prueba: las lecturas programadas del simulador (con retraso de SQS) traían las fallas del inicio del minuto y "reparaban" antenas forzadas por un escenario → incidentes que se cerraban y reabrían. Ahora, al procesarlas, se aplican las fallas vigentes (`motor_antenas.vigentes`).

## Cómo se desplegó (con cuidado: última cuenta disponible)
1. Revisión de solo lectura de la cuenta: límite real de AWS 1000 (el de 10 lo vigila Vocareum por fuera), 5 Lambdas propias del lab.
2. Despliegue por stacks, compilando cada plantilla antes (`serverless package`) para revisar funciones, topes y que no hubiera recursos personalizados.
3. AWS rechazó `maximumConcurrency: 2` > tope 1 (CREATE_FAILED, rollback sin ejecutar nada) → se quitó y se agregó una prueba.

## Resultados medidos (CloudWatch `ConcurrentExecutions`, máximo de la cuenta)
| Momento | Máximo |
|---|---|
| Arranque del lab (Lambdas de Vocareum) | 2 |
| Despliegue de los 4 stacks + frontend | 1 |
| Simulación acelerada 1 (86 reportes, panel abierto) | 6 |
| Simulación acelerada 2, con la corrección | 5 |
| **Máximo absoluto de la cuenta** | **6** (límite 10) |

- 86/86 y 78/78 reportes registrados; DLQ de reportes, métricas y detector en 0; 0 Step Functions fallidas.
- Segunda simulación: exactamente 4 incidentes (uno por evento), todos cerrados solos.
- `Throttles` (veces que algo esperó su turno en vez de abrir otra Lambda) altos en segundo plano y simulador: es el tope funcionando; no son ejecuciones y no cuentan para el límite.

## Pendiente
- El simulador quedó **apagado** (encenderlo desde el mapa para la demo).
- No ejecutar `scripts/demo/carga.py` con valores altos: con los topes no rompe la cuenta, pero la cola tarda en vaciarse.
- Azure sin configurar en esta cuenta (falta el secreto de Rodrigo).
- Dos simulaciones seguidas pueden juntar 10 reportes de "ruido" en una zona tranquila en 24 h (regla del reto) → incidente sin antenas que queda en evaluación; se cierra con "Reiniciar demo".

## Notas para los otros agentes
- **No agregues Lambdas** sin quitarle cupo a otra: `pytest` falla. Las rutas nuevas van en `services/api/src/router.py`; los pasos nuevos de Step Functions, en `workflows/src/motor.py` con `"accion"`.
- `serverless.yml`: `maximumConcurrency` de SQS no puede ser mayor que `reservedConcurrency` (AWS lo rechaza).
