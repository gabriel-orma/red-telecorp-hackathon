# Roadmap por entregas

Se construye **todo** lo del spec, pero **por entregas**. Cada entrega termina desplegada en AWS y con una lista de **qué probar**. La siguiente empieza solo cuando el equipo prueba la anterior y da su feedback (sobre todo de diseño).

El orden sigue tres criterios:
1. Lo que **descalifica** o vale más en la rúbrica.
2. Lo que se ve **pronto en pantalla**, para iterar el diseño.
3. Las dependencias técnicas.

Leyenda: ⬜ pendiente · 🟨 en curso · 🧪 lista para probar · ✅ aprobada por el equipo

---

## E0: Verificación del Learner Lab ✅
> Resultados en [D1](decisiones/2026-11-13-aws-academy-us-east-1.md#verificación-del-lab-e0-2026-11-14-issue-8): CloudFront, SES, SMS, Bedrock y Comprehend bloqueados; el resto funciona.
Un stack de humo que confirma qué servicios funcionan con `LabRole` antes de construir encima.
- Lambda (`python3.12`), HTTP API, **WebSocket API**, DynamoDB (Streams, PITR, TTL), SQS + DLQ, Step Functions, EventBridge Scheduler, SNS (email y SMS), SES, S3, **CloudFront**, Secrets Manager, SSM.
- **Probar**: tabla de resultados ✅/❌ en la decisión D1, con una alternativa para cada servicio bloqueado.

## E1: Mapa en vivo (primer vistazo del diseño) ✅
> Feedback: aprobado. **Pendiente de pulir más adelante: fuentes y algunos detalles de CSS.**
- Catálogo de **zonas reales de Lima** (centro y radio) y **~35 antenas con coordenadas**. Requiere un cambio de contrato.
- Stack `base`: tablas, colas + DLQ, SSM, Secrets Manager y el layer común.
- Stack `antenas`: simulador (EventBridge, **apagado por defecto**) y clasificador (0 / <60 / 60–129 / >129).
- API: `GET /antenas`, `GET /zonas`.
- **Frontend base** (React + Vite + Tailwind + shadcn/ui, modo oscuro) en S3 + CloudFront:
  - layout del centro de control;
  - **mapa MapLibre** con las antenas en color (verde normal, amarillo saturada, rojo caída, gris inhabilitada);
  - polling cada 3 s.
- `scripts/deploy.sh` y `remove.sh`: todo replicable.
- **Probar**: abrir la URL, encender el simulador, forzar una falla y ver la antena cambiar de color. → **Feedback de diseño.**

## E2: Portal del usuario + gestión de incidencias ✅
- `POST /reportes` → SQS → worker, **idempotente** (el mismo usuario no cuenta doble).
- `GET`/`PATCH` de incidencias, transiciones válidas e **historial inmutable**.
- Portal móvil:
  - formulario con **geolocalización + selector en el mapa**;
  - pantalla de seguimiento **tipo "pedido en camino"** (línea de tiempo del historial);
  - estado de la zona del usuario.
- Panel: lista de incidencias con cambio de estado + **mapa de calor** de reportes.
- **Probar**: reportar desde el celular, seguir el reporte y cambiarle el estado desde el panel.

## E3: Detección colectiva + Step Functions ✅
- Detector: **≥10 usuarios distintos / zona / <24 h** y **detección proactiva** por antena caída o inhabilitada.
- **Step Function `incidente-colectivo`**:
  - `Choice` (¿crítico?, ¿hay antenas en falla?);
  - `Map` para notificar a cada afectado;
  - `Wait` + **re-verificación** de las antenas;
  - restablecimiento automático o manual y cierre;
  - reintentos con backoff.
- Notificaciones por estado (en evaluación / identificada / restablecida) por el canal que permita el lab.
- Frontend:
  - **zonas que pulsan**;
  - **diagrama del flujo** con el paso actual resaltado;
  - **banner y alerta sonora** al detectarse un colectivo;
  - detalle del incidente.
- **Probar**: 12 reportes en una zona → alerta, diagrama avanzando, notificaciones registradas.

## E3.5: Estado público + cuentas de usuario ✅
> Pedido del equipo antes de la 2.ª nube.
- **Página pública estilo Downdetector** (`/portal`):
  - semáforo general y por zona;
  - gráfico de 24 h contra la línea base;
  - problemas más reportados, zonas con más reportes, mapa e incidentes activos.
- **Cuentas con Cognito** (D9): registro en un paso y reporte mínimo (**tipo + descripción**). Ubicación automática (GPS → zona de la cuenta); "mis reportes".
- **Contadores agregados** por bloque de 15 min (D10).

## Rediseño de la UI (D11) ✅
> Estilo neumórfico oscuro aprobado por el equipo, aplicado a todas las pantallas (#28).

## E5: Simulación de tormenta + resiliencia ✅
- **Step Function `escenario`** ("tormenta" y "corte de energía" por zona): genera reportes y caídas escalonadas durante ~60 s.
- Botones **"Simular tormenta"** y **"Reiniciar demo"** (datos semilla).
- **Propagación animada** desde la antena caída (círculo del área afectada) y **contadores animados**: afectados, antenas caídas, tiempo promedio de detección.
- **Prueba de carga** (cientos de reportes en segundos): DLQ vacía, sin pérdidas.
- **Probar**: presionar "Simular tormenta" y ver cómo se llena el mapa en vivo.

## E6: Inteligencia operativa 🧪
- **Correlación**: tarjeta "**detectado X min antes que el primer reporte**".
- **Puntaje de prioridad** (afectados × criticidad × tiempo activo; D7) → **lista ordenada** con colores.
- **Step Function `recurrencia`** (diaria): antenas con N fallas en 7 días → **problema estructural**.
- **Analítica**: zonas con más incidentes, antenas más problemáticas, tipos más frecuentes, duración y afectados (Recharts).
- **Probar**: el panel de analítica con datos de las entregas anteriores.

## E7: Tiempo real y experiencia avanzada ⬜
- **WebSocket API** para el panel, con **polling de respaldo** y limpieza de conexiones caídas.
- **Asistente conversacional** del operador ("¿qué zona atiendo primero?") con datos reales.
- **Reproducción del historial** con un deslizador de tiempo.
- **Reporte por voz** (API de voz del navegador).
- Mapa de calor 3D / **extrusión** de zonas (MapLibre).
- Paleta de comandos `Ctrl+K`, modo pantalla grande, alto contraste.

## E8: Extras de alcance ⬜
- **Bot de Telegram** para reportar.
- **PWA** instalable + notificaciones push.
- Multiidioma (ES/EN).

## E4: Segunda nube + IA (requiere D2) ⬜ — **movida al final** (decisión del equipo, 2026-11-14)
> **Orden actualizado:** primero la app completa en AWS (E5–E8) y al final se "traduce" a la 2.ª nube. Mientras tanto, cada función de IA queda detrás de un enchufe con implementación provisional, el histórico se exporta a S3 y la API key ya tiene su secreto. **Conseguir la cuenta de la 2.ª nube desde ya.**
> **Sin 2 nubes no se corrige el proyecto**, y la IA vale 3 puntos. Por eso va antes que lo vistoso. Si D2 no está decidida a tiempo, se intercambia con E5.
- Servicio en la 2.ª nube, invocado por HTTPS con la API key en **Secrets Manager**:
  - **reporte en lenguaje natural → la IA rellena el formulario**;
  - **resumen del incidente** (tarjeta de IA);
  - **mensajes de notificación redactados por la IA**;
  - apoyo a la prioridad según el tipo de zona.
- **Réplica del histórico**: al cerrarse un incidente → S3 (versionado) + almacén analítico en la 2.ª nube.
- **Probar**: escribir "no tengo internet hace una hora en San Isidro" y ver el formulario lleno; ver la tarjeta de IA.

## E9: Demo y entrega ⬜
- Diagrama de arquitectura final (una flecha por flujo).
- Costo estimado (≈ $0 sin uso).
- Guion de 4:30, ensayo, **grabación de respaldo**.
- Entrega en Canvas: video + repo + arquitectura. **Sin informe.**

---

### Reglas de costo en todas las entregas
- Nada encendido 24/7. El simulador se enciende solo para pruebas y la demo.
- La IA se llama solo con eventos de valor (un reporte en lenguaje natural, un colectivo nuevo), nunca por cada métrica.
- Retención de logs de 7 días, TTL en las métricas y `serverless remove` de los stages que no se usen.
