# Fase final: datos simulados vs operativos, incidentes en atención manual y revisión del frontend

- **Autor**: rodrigo (+ Claude Code)
- **Fecha**: 2026-11-15
- **Issue / PR**: PR a `main` (apilado sobre #45; ver la nota de integración)
- **Rama**: `exp/rod-final`

## Qué se hizo
- **Separación de lo simulado y lo operativo (D13)**: una sola definición (`reglas.es_simulado`); el detector, las estadísticas, la analítica, la recurrencia y el estado público trabajan cada uno con su universo. Ventana y candado por modo (`~SIM`), series `SIM#…`, `?datos=operativos|simulados`, la recurrencia simulada no alerta al NOC, «Reiniciar demo» ya no cierra incidentes de usuarios reales. No se borra ni reescribe ningún dato. Detalle y alternativas: `docs/decisiones/2026-11-15-separacion-simulado-operativo.md`.
- **Incidentes en `REQUIERE_ATENCION`**: antes se veían pero no se podían cerrar (la zona quedaba sin dueño). `POST /api/colectivos/{id}/restablecer` los retoma: vuelve a reservar la zona (409 si ya hay otro abierto), arranca una ejecución `reanudar` y el cierre es el flujo normal (avisos de «restablecido», incidencias solucionadas, historial, candado). Reversible si falla Step Functions. El estado público ya no los da por resueltos.
- **Frontend** (revisión en navegador real contra una maqueta local, porque las credenciales del lab habían caducado): etiqueta «Simulado» (colectivos, antenas), selector Operativos/Simulación en la analítica, aviso «hay una simulación en curso» en el estado público, retomar un incidente con confirmación y resultado, errores visibles en lugar de spinners, controles de fallas forzadas solo para operadores, `usePolling` recarga al cambiar de zona o rango, el editor de la línea de tiempo ya no secuestra Espacio/flechas de sus botones, contraste del degradado (≥ 4,5:1), `aria-pressed`/`aria-current`, títulos de pestaña, nombre accesible del logotipo, `ErrorBoundary`, `reducedMotion="user"`, etiquetas del mapa escapadas.
- **Privacidad, sesión y teclado** (verificados en el navegador contra el backend real de `dev-rodrigo`): la ubicación sale redondeada a ≈110 m (3 decimales) y sin alta precisión; las consultas públicas de lectura ya no llevan el ID token; una sesión caducada (refresh token rechazado o 401 con sesión) muestra un aviso con salida y un fallo de red ya no cierra la sesión; el detalle de incidencias recibe el foco al abrirse, Esc lo cierra devolviendo el foco a su fila; enlace «Saltar al contenido».
- **Comparación de modelos de ML**: va en otro PR (`docs/rod-ml-comparacion`): se conserva el modelo actual.

## Archivos y recursos tocados
`services/base/layer/python/telecorp/{reglas,historial,estadisticas}.py`, `services/antenas/src/{simulador,clasificador}.py`, `services/api/src/{analitica,estado,colectivos,escenarios,incidencias,antenas}.py`, `workflows/src/{comun_colectivos,detector,pasos,recurrencia}.py`, `contracts/schemas/*` (solo campos opcionales nuevos), `frontend/src/**`, `scripts/reclasificar-simulados.py`, docs. **Sin recursos nuevos de AWS**: usa la tabla `dedup` y las series de `estadisticas` existentes.

## Cómo probarlo
```bash
pytest                                 # 416 pruebas (28 nuevas de separación y atención manual)
cd frontend && npx tsc -b && npx vite build
```
En la nube (stage `dev-rodrigo`, **pendiente**: las credenciales del lab caducaron durante esta sesión): desplegar, correr la regresión E2E y comprobar con una Tormenta que el estado público y la analítica operativa no cambian.

## Decisiones tomadas
- D13 (ver arriba). Cambios de contrato **aditivos** (campos opcionales): requieren el OK de la otra persona según `AGENTS.md` §4; si se prefiere un PR solo de contratos, el commit `contracts(...)` se separa sin tocar nada más.

## Defectos conocidos (por severidad)
**Importantes (abiertos)**
- Los contadores de `estadisticas` y el historial de antenas anteriores a D13 no se pueden separar: en un stage con pruebas antiguas, «Operativos» puede incluir datos de prueba (`scripts/reclasificar-simulados.py` solo reclasifica colectivos). Un stage limpio no tiene el problema.
- Los reportes enviados con `scripts/demo/reportar.py` y `carga.py` entran por el camino real con cuentas `demo.*@example.com`: cuentan como **operativos**. No se clasifican por dominio de correo para no etiquetar mal a un evaluador que pruebe con `@example.com`.
- Accesibilidad aún abierta: el mapa (MapLibre) no tiene navegación por teclado propia, bucle de animación del mapa sin respetar `prefers-reduced-motion`, textos de contraste bajo (`text-tenue/60`, SIN_DATOS), el detalle de colectivos no gestiona el foco como el de incidencias.
- Mapa: si falla el estilo de CartoCDN el mapa queda vacío sin aviso.

**Cosméticos**: «Nubes conectadas» cuenta PARCIAL como operativa (está explicado en pantalla); doble pedido de `/colectivos` y `/estado` en algunas pantallas; barra móvil de 8 botones < 44 px.

**Sin verificar en la nube todavía**: PITR (restauración), redrive de la DLQ, alarmas de CloudWatch, prueba de carga con los cambios, y las 10 jornadas E2E sobre esta rama.

## Pendiente / siguiente paso
- Renovar credenciales del lab, desplegar en `dev-rodrigo` (no en el stage de Gabriel), correr la regresión y repetir las capturas con un stage limpio.
- Confirmar con Gabriel el stage único antes del video.

## Notas para los otros agentes
- Cualquier lectura nueva de colectivos, estadísticas o antenas debe decidir en qué universo está (`reglas.es_simulado`); no mezclarlos.
- `colectivo_abierto`, `crear`, `liberar_lock`, `leer_ventana`, etc. aceptan `sim` (por defecto operativo).
