# El reto: Red TeleCorp

## Contexto
Red TeleCorp es una telco (telefonía móvil, Internet y conectividad) con millones de usuarios en distintas ciudades y zonas. Recibe información de tres fuentes: **métricas de antenas**, **reportes de usuarios** y **registros de sistemas internos**. En ciertos periodos el volumen crece mucho.

## Requisitos del cliente

### Antenas (simulación)
Cada antena reporta periódicamente su tráfico en **GB por minuto**:

| Tráfico | Estado |
|---|---|
| `= 0` | **Inhabilitada** |
| `< 60` | **Caída** |
| `60 – 129` | Normal |
| `> 129` | **Saturada** |

### Portal de incidencias para usuarios
- Datos del reporte: identificación, número asociado al servicio, ubicación aproximada, fecha y hora, tipo de problema y descripción.
- Las incidencias se consultan y administran posteriormente.
- Estados: **registrada, en revisión, siendo atendida, solucionada, cerrada**.
- **Historial** de cómo evolucionó cada incidente.

### Incidente colectivo
- **10 o más usuarios diferentes**, en la **misma zona**, en **menos de 24 horas** → posible incidente colectivo → verificar la infraestructura correspondiente.

### Notificaciones
- Los usuarios que reportaron reciben comunicación por **correo y/o celular**.
- Mensajes según el estado: *se está evaluando*, *se identificó una incidencia en la zona* o *el servicio fue restablecido*.

### Priorización
- Según la **cantidad de afectados** (5 personas ≠ miles).
- Según el **tipo de zona**: residencial, industrial, institución educativa, centro médico, servicios críticos.

### Analítica
- Zonas con más incidentes, antenas con más problemas, tipos de inconveniente más frecuentes.
- **Recurrencia**: una antena con varios incidentes en días distintos que "se recupera" puede tener un problema estructural.
- **Histórico**: evolución de los incidentes, tiempo activo, zonas afectadas, usuarios involucrados y frecuencia por elemento de infraestructura.

### Detección temprana
- Reducir el tiempo entre la aparición de un problema y su identificación, para no enterarse primero por los usuarios.
- **Correlacionar** los reportes de usuarios con el comportamiento de la infraestructura.

### Picos de carga
- Cortes de energía, eventos climáticos o fallas masivas generan muchos reportes en minutos. **No se puede perder ningún registro** ni degradar el servicio.

### Costo
- Menor costo operativo posible, que escale con usuarios y eventos y **sin infraestructura permanentemente encendida**.

## Rúbrica (20 pts)

| Criterio | Pts |
|---|---|
| Resolver la mayor cantidad de problemas del contexto | 0–3 |
| Persistencia y alta disponibilidad de los datos | 0–2 |
| Uso de Step Functions para automatización | 0–2 |
| Uso de 2 nubes o más | 0–3 |
| Arquitectura de la solución | 0–3 |
| Pitch de 5 minutos | 0–2 |
| Solución completamente serverless | 0–2 |
| Uso de IA en la solución | 0–3 |

## Notas obligatorias
- Si el video pasa de **5 minutos**, no se revisa el proyecto.
- Se entrega por Canvas: **el video, el repo de GitHub y la arquitectura**.
- **Si se entrega un informe, se anula la participación.**
- **Sin al menos 2 nubes no se corrige** (Vercel no cuenta).
- Usar un **servicio de AWS para proteger las variables globales y secretos**.
- "Es un curso de Cloud Computing, no de Ingeniería del Prompt."
