# E7: Tiempo real y experiencia avanzada

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 11:20
- **Issue / PR**: #36
- **Rama**: feat/36-e7-tiempo-real

## Qué se hizo
- **WebSocket API** (API Gateway) + tabla `conexiones` (TTL) + **difusor** sobre los streams de antenas, colectivos (stream nuevo, KEYS_ONLY) e incidencias.
  - Un aviso liviano por tipo y lote; antenas como máximo 1 cada 2 s por contenedor.
  - Las conexiones que ya no existen se borran (limpieza).
- **Frontend**:
  - conexión compartida con reconexión;
  - **polling adaptativo**: 30 s con WebSocket y 3 s sin él;
  - indicador "En vivo · WebSocket / polling".
- **Reproducción del historial** de un incidente (deslizador + play).
- **Reporte por voz** en el portal.
- **Mapa 3D** (extrusión de zonas por reportes).
- **Modo sala** y **alto contraste**.
- Se corrigió el conteo de pruebas de la bitácora de E6 (38) y `pytest.ini` vuelve a mostrar la línea de resumen.
- El asistente conversacional del operador pasa a E4 (necesita IA).

## Resultados en el lab
- Cliente WebSocket de prueba: aviso de **antenas a 1,5 s** de forzar una falla; aviso de **colectivo a 7,6 s** (el detector crea el incidente proactivo).
- Navegador: "En vivo · WebSocket", 3D con columnas por zona, reproducción en marcha, alto contraste activo.

## Pendiente / siguiente paso
- E8: extras de alcance (Telegram, PWA, multiidioma).

## Notas para los otros agentes
- En API Gateway WebSocket, la respuesta de la Lambda **no** llega al cliente salvo que la ruta tenga "route response": el ping no espera respuesta.
- Un stream de DynamoDB admite 2 consumidores a la vez: incidencias y antenas ya tienen 2 (detector + difusor). Para un tercero, usar Kinesis o EventBridge Pipes.
- El difusor también está en `scripts/reactivar-lab.sh`.
