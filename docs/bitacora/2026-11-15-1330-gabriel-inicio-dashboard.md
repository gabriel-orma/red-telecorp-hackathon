# Inicio (dashboard) y botones para volver desde el portal

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-15 13:30
- **Rama**: feat/dashboard-navegacion (sobre la integración de la fase final de Rodrigo, aún no fusionada en `main`)

## Qué se hizo
- Nueva pantalla **Inicio** en `/`, que ahora es la pantalla de inicio de la app: estado general, 4 indicadores con enlace, gráfico de reportes de 24 h contra lo normal, cola de atención, zonas por gravedad y accesos a las 8 pantallas.
- El mapa en vivo se movió a `/mapa`; se actualizaron los enlaces de la paleta Ctrl+K, la analítica y la línea de tiempo.
- Portal y estado público: botón **Inicio** para volver al panel. En celular la barra del portal muestra solo íconos (antes "Ingresar" se cortaba).
- `.claude/launch.json`: frontend local con el API desplegado como proxy.

## Cómo probar
`VITE_API_PROXY=<url del API> npm --prefix frontend run dev` y abrir `/`, `/portal`, `/mapa`.
Verificado en el navegador en escritorio y celular (375 px, sin scroll horizontal).

## Pendiente
- La barra inferior en celular ya tiene 10 íconos: conviene agrupar (por ejemplo, un menú "Más").
- No desplegado: la sesión del Learner Lab se cerró.
