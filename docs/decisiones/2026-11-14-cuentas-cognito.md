# D9: Cuentas de usuario con Amazon Cognito

- Estado: aceptada
- Issue: #25

## Contexto
El equipo quiere un reporte con el mínimo esfuerzo: el usuario solo elige **tipo + descripción**. La ubicación es automática y el resto de los datos sale de **su cuenta**.

## Decisión
- **Cognito User Pool** (`telecorp-<stage>-usuarios`):
  - inicio de sesión con email;
  - atributos `name`, `phone_number` y los custom `dni`, `numeroServicio`, `zonaId`, `avisosEmail`.
- Trigger **PreSignUp**: valida el perfil (DNI de 8–12 dígitos, zona del catálogo, teléfono E.164) y **auto-confirma** la cuenta. Registro en un paso, decidido por el equipo para la demo: no se verifica que el correo sea real.
- El HTTP API usa un **autorizador JWT** que valida el **ID token** (audience = client id). El backend toma los datos personales de los *claims*, no del cuerpo de la petición.
- La ubicación del reporte sale del **GPS** del navegador. Si no hay permiso o el punto cae fuera de cobertura, se usa la **zona del servicio de la cuenta** (`ubicacionFuente: GPS | CUENTA`).
- El frontend llama a la **API JSON de Cognito directamente** (`SignUp`, `InitiateAuth`, refresh), sin SDK. Los tokens se guardan en `localStorage`.
- El **panel del operador sigue abierto** por ahora (datos enmascarados). Pendiente: grupo `operadores` en Cognito.

## Consecuencias
- `POST /api/reportes` y `GET /api/mis-reportes` devuelven **401** sin token.
- Los scripts de demo crean usuarios `demo.<dni>@example.com` (SignUp e InitiateAuth no requieren credenciales de AWS).
- Verificado en Learner Lab: Cognito permite crear pools, registrar, confirmar e iniciar sesión.
