# E3.5: Estado público estilo Downdetector + cuentas de usuario

- **Autor**: gabriel (+ Claude Code)
- **Fecha**: 2026-11-14 02:30
- **Issue / PR**: #25 (contrato #24 / PR #26)
- **Rama**: feat/25-estado-cuentas

## Qué se hizo
- **Cognito** (D9):
  - User Pool con atributos de perfil;
  - trigger **PreSignUp** que valida y auto-confirma;
  - **autorizador JWT** en el HTTP API.
- **Reporte mínimo**: `POST /api/reportes` solo recibe `{tipo, descripcion, ubicacion?}`. Los datos salen del ID token y la zona del GPS (o de la cuenta, `ubicacionFuente`). Nuevo `GET /api/mis-reportes` (GSI `usuario-fecha`).
- **Estadísticas** (D10): tabla `estadisticas` con contadores de 15 min (`ADD` atómico desde el worker). Nuevo `GET /api/estado`, público y con caché, que devuelve el semáforo, la serie de 24 h contra la línea base de 7 días, los tipos, las zonas y los incidentes.
- **Frontend**:
  - `/portal` como **página pública de estado** (gráfico Recharts con la línea base punteada, tipos, ranking, mapa por nivel, incidentes, botón "Tengo un problema");
  - `/portal/cuenta` (ingresar/registrarse/mis reportes) y `/portal/reportar` (tipo + descripción, ubicación automática);
  - autenticación directa contra la API JSON de Cognito.
- **Demo**: `historico.py` (8 días de contadores de demo) y `reportar.py`, que ahora usa cuentas demo de Cognito.

## Pruebas
- `pytest`: 32 pruebas (buckets, línea base, semáforo, construcción del reporte desde los claims, PreSignUp).
- En el lab:
  - `POST` sin token → **401**; registro con un DNI de 7 dígitos → rechazado por PreSignUp;
  - reporte sin GPS → zona de la cuenta (`CUENTA`); con GPS → zona del GPS;
  - 12 reportes demo en ZONA-05 → `/api/estado` en **PROBLEMAS** (14 en la última hora contra 2 normales) + el colectivo de E3.
- En el navegador: página de estado con el pico sobre la base; redirección a "Cuenta" al intentar reportar sin sesión.

## Pendiente / siguiente paso
- Login del operador (grupo `operadores`).
- E4: segunda nube + IA (D2).

## Notas para los otros agentes
- Un `package.patterns: ["!**", ...]` a nivel de servicio **también vacía los layers** de ese servicio: usa solo exclusiones.
- Crear un GSI en una tabla existente tarda varios minutos (`CREATING`): las consultas al índice fallan hasta que pase a `ACTIVE`.
- Router: un componente hijo puede navegar en su `useEffect` **antes** de que el `useEffect` de App registre el listener; `useRuta` se re-sincroniza al montarse.
- El autorizador valida el **ID token** (tiene `aud` = client id y los atributos `custom:*`); el access token no sirve aquí.
