# Instrucciones para agentes de IA (y humanos)

Este archivo es la **fuente única de reglas** del repo. Lo leen Claude Code (vía `CLAUDE.md`), Codex, Cursor, Gemini CLI (vía `GEMINI.md`) y cualquier chatbot al que le pegues contexto. Si usas un chatbot sin acceso al repo, **pégale este archivo y `docs/arquitectura.md` antes de pedirle nada**.

Somos 3 personas trabajando **en paralelo**, cada una con su propio agente. El mayor riesgo no es el código: es que tres agentes inventen tres versiones distintas del mismo sistema. Estas reglas existen para evitarlo.

---

## 1. Contexto del proyecto (resumen)

Hackathon de Cloud Computing (UTEC). Cliente ficticio: **Red TeleCorp**, una telco. Construimos una plataforma **100 % serverless y multinube** que:

- Ingiere métricas de antenas y las clasifica (GB/min): `0` = **inhabilitada**, `<60` = **caída**, `60–129` = **normal**, `>129` = **saturada**.
- Ofrece un portal donde los usuarios reportan incidencias (identificación, número de servicio, ubicación aproximada, fecha y hora, tipo, descripción).
- Gestiona incidencias con estados `REGISTRADA → EN_REVISION → EN_ATENCION → SOLUCIONADA → CERRADA` e **historial** de cada cambio.
- Detecta **incidentes colectivos**: 10 o más usuarios **distintos** en la **misma zona** en **menos de 24 h**.
- Notifica a los afectados (email/SMS) según el estado del incidente.
- Prioriza por cantidad de afectados y criticidad de la zona (hospital, colegio, industrial, residencial…).
- Detecta antenas con incidentes **recurrentes** (problema estructural).
- Correlaciona reportes de usuarios con métricas de antenas.
- Soporta picos masivos sin perder registros.
- Ofrece analítica histórica (zonas, antenas, tipos, duración, afectados).

Detalle completo: [`docs/reto.md`](docs/reto.md). Arquitectura: [`docs/arquitectura.md`](docs/arquitectura.md).

### Restricciones de la rúbrica (no negociables)
- **2 nubes o más** (Vercel **no** cuenta). AWS es la nube principal. La segunda está **por definir** (decisión D2).

### Stack decidido (ver [`docs/decisiones/`](docs/decisiones/README.md))
- **AWS Academy Learner Lab** en **`us-east-1`**. No se pueden crear roles IAM: **todo usa `LabRole`**.
- **Serverless Framework** como IaC, con un `serverless.yml` por servicio.
- **Python** para todas las Lambdas.
- **DynamoDB con tablas separadas** (incidencias, historial, métricas, incidentes colectivos).
- Aún abiertas: segunda nube (D2), frontend (D5), fórmula de prioridad y umbral de recurrencia (D7). No las asumas.
- **Todo serverless**: nada de EC2, VMs ni contenedores encendidos 24/7.
- **Step Functions** para automatizar flujos.
- **Secretos en un servicio de AWS** (Secrets Manager o SSM Parameter Store). **Nunca** en el código ni en el repo.
- **IA** como componente de la solución, no como sustituto del diseño.
- **Prohibido entregar un informe.** La documentación del repo (README, docs) está bien; un "informe" anula la participación.
- Costo operativo mínimo: servicios que se paguen por uso.

---

## 2. Protocolo de sesión (OBLIGATORIO)

### Al iniciar cada sesión
1. **Sincroniza** antes de tocar nada:
   ```bash
   git fetch origin && git status
   git switch main && git pull --rebase origin main
   ```
   Si estás en una rama de trabajo: `git rebase origin/main`.
2. **Lee lo nuevo**:
   - Las últimas entradas de [`docs/bitacora/`](docs/bitacora/) (ordenadas por nombre = fecha).
   - [`docs/decisiones/`](docs/decisiones/), por si algo cambió.
   - [`contracts/`](contracts/), si vas a producir o consumir datos.
3. **Revisa la coordinación**: `gh issue list --state open`. Mira sobre todo los labels `ayuda`, `contrato`, `decision` y `bloqueado`.

En Claude Code, `/sync` hace todo esto.

### Antes de empezar una tarea
1. Debe existir un **issue** para la tarea. Si no existe, créalo (plantilla "Tarea").
2. **Reclámala**: asígnate el issue, ponle el label `en-progreso` y escribe en el cuerpo la **zona de archivos** que vas a tocar (carpetas o archivos concretos).
3. Revisa que ningún otro issue `en-progreso` declare esos mismos archivos. Si se cruzan, **coordina en el issue antes de seguir**.
4. Crea una rama: `feat/<n°issue>-<slug>`, `fix/<n°issue>-<slug>` o `docs/<n°issue>-<slug>`.

En Claude Code: `/tomar <n°issue o descripción>`.

### Mientras trabajas
- Commits pequeños y frecuentes, con mensajes en español e imperativo: `feat(reportes): agrega validación de zona (#12)`.
- Haz **`git fetch && git rebase origin/main`** al menos cada vez que termines un bloque de trabajo. Ramas cortas = menos conflictos.
- **No edites archivos fuera de tu zona declarada.** Si lo necesitas, pide ayuda o amplía tu zona avisando en el issue.
- **No cambies `contracts/` por tu cuenta.** Ver §4.

### Al terminar
1. **Documenta** (§3): una entrada de bitácora, más la doc de lo que construiste.
2. Rebase sobre `origin/main` y corre las pruebas o el linter de tu área.
3. Push y **PR** con la plantilla. El PR cierra el issue (`Closes #N`).
4. Quita `en-progreso` y deja un comentario con el resumen.

En Claude Code: `/cerrar`.

---

## 3. Documentación: todo lo que se hace queda escrito

**Regla: si no está documentado, no existe.** El agente de otra persona no ve tu conversación; solo ve el repo y los issues.

| Qué | Dónde | Cuándo |
|---|---|---|
| Qué hiciste en la sesión | `docs/bitacora/AAAA-MM-DD-HHMM-<autor>-<slug>.md` | Al terminar **cada** sesión o tarea |
| Una decisión técnica (servicio, librería, patrón, cambio de diseño) | `docs/decisiones/AAAA-MM-DD-<slug>.md` | Al tomarla, y siempre con un issue `decision` |
| Cómo usar o desplegar un módulo | `README.md` dentro de la carpeta del módulo | Al crearlo y cada vez que cambie |
| Forma de los datos y eventos | `contracts/` | Solo mediante el proceso de §4 |
| Recursos cloud nuevos (tabla, cola, bucket, función) | Sección "Inventario" en `docs/arquitectura.md` | En el mismo PR que los crea |
| Avance sobre los dolores del cliente | Columna "Estado" en `docs/mapa-dolores.md` | Cuando un dolor pasa a cubierto |

- **Un archivo por entrada** en la bitácora y en las decisiones: así nunca hay conflictos de merge.
- Plantilla de bitácora: [`docs/bitacora/_plantilla.md`](docs/bitacora/_plantilla.md).
- Escribe para alguien (persona o IA) que **no estuvo** en tu sesión: qué cambió, dónde, cómo probarlo y qué quedó pendiente.

---

## 4. Contratos compartidos (`contracts/`)

`contracts/` define la forma de los datos que cruzan entre módulos: reportes, métricas, incidentes, eventos y catálogo de zonas. Es lo que permite trabajar en paralelo con *mocks* sin esperar a los demás.

- **Programa contra los contratos, no contra la implementación de otro.** Si dependes de algo que aún no existe, crea un mock que cumpla el contrato.
- Para **cambiar** un contrato:
  1. Abre un issue con el label `contrato` (plantilla "Cambio de contrato") que explique el qué, el porqué y a quién afecta.
  2. Espera el OK de al menos otra persona en el issue.
  3. Haz el cambio en un PR **solo de contratos**, actualizando los ejemplos.
- Los cambios aditivos (un campo opcional nuevo) se aprueban rápido. Los que rompen compatibilidad (renombrar, borrar o cambiar tipos) requieren el OK de **todos**.

---

## 5. Comunicación entre agentes: pedir y ofrecer ayuda

Los agentes no comparten memoria. **Se comunican a través de GitHub Issues**, que todos (personas y agentes) pueden leer y escribir con `gh`.

### Pedir ayuda (`/ayuda` en Claude Code)
Cuando necesites algo que **está fuera de tu zona de archivos** o te bloquea, abre un issue con el label `ayuda` (plantilla "Pedido de ayuda") con:
- **Qué necesitas**, concreto y verificable ("un endpoint `GET /incidencias?zona=` que devuelva `contracts/incidencia`").
- **Zona de archivos sugerida** para quien lo haga, que **no debe cruzarse** con la tuya.
- **Contrato** involucrado.
- **Qué haces mientras tanto** (normalmente, seguir con un mock).
- Si te bloquea, agrega el label `bloqueado`.

### Ofrecer o tomar ayuda (`/atender` en Claude Code)
- Revisa los issues `ayuda` abiertos y sin asignar.
- Antes de tomarlo, verifica que su zona de archivos no choque con ningún issue `en-progreso`.
- Asígnatelo y comenta "lo tomo". Desde ahí sigue el flujo normal (§2).

### Reglas de convivencia
- **Nunca** reescribas, reformatees ni "mejores" código de otra zona sin un issue. Si ves un bug ajeno, abre un issue.
- Si un agente tuyo propone tocar `AGENTS.md`, `contracts/` o la arquitectura, **detente y crea un issue** `decision` o `contrato`.
- Los issues son la conversación persistente. Si algo se habló por WhatsApp o en persona, **resúmelo en el issue**.
- Sin `gh`, la persona humana crea el issue en github.com. El agente le redacta el texto.

---

## 6. Git: reglas para no pisarse

- `main` siempre debe desplegar. **Nadie hace push directo a `main`**: todo entra por PR.
- Merge con **squash**. Borra la rama después del merge.
- Ante un conflicto: `git rebase origin/main` y resuélvelo **conservando el trabajo de ambos**. Si el conflicto está en una zona ajena, pregunta en el issue de esa persona. **Nunca** uses `git push --force` sobre `main`; sobre tu propia rama usa `--force-with-lease`.
- No hagas commit de: secretos, `.env`, credenciales, `node_modules`, `.aws-sam`, `.serverless`, builds ni archivos de más de 5 MB.

---

## 7. Cloud: reglas de despliegue

- **AWS Academy Learner Lab**: cada persona tiene su propia cuenta de laboratorio.
  - **Nunca intentes crear roles IAM**: en Serverless, `provider.iam.role: arn:aws:iam::${aws:accountId}:role/LabRole`, y lo mismo en las Step Functions.
  - Las credenciales caducan con cada sesión del lab: si un despliegue falla por credenciales, pide a tu humano que actualice `~/.aws/credentials` desde *AWS Details*.
  - Detalles y servicios posiblemente restringidos (SES, SNS SMS…): [decisión D1](docs/decisiones/2026-11-13-aws-academy-us-east-1.md).
- **Cada persona despliega en su propio stage** (`dev-<alias>`) en su propia cuenta. Solo existe un stage compartido, `demo`: se despliega desde `main` en una única cuenta, que está documentada en la decisión D1.
- **Nombres**: tablas, colas y buckets se nombran explícitamente `telecorp-<stage>-<recurso>` (ej.: `telecorp-dev-gabo-incidencias`). Las Lambdas usan el nombre por defecto de Serverless (`telecorp-<dominio>-<stage>-<función>`).
- **Región AWS**: `us-east-1`, fija. La 2.ª nube está por definir (D2).
- **Secretos** (API keys de Gemini, credenciales de GCP, etc.) en **AWS Secrets Manager / SSM Parameter Store**, leídos en tiempo de ejecución. En local, `.env` (ignorado por git), siguiendo `.env.example`.
- **Infraestructura como código**: todo recurso se crea con **Serverless Framework**, un `serverless.yml` por servicio. Un recurso compartido lo crea **un solo** servicio y lo exporta como `Output`; los demás lo leen con `${cf:...}`. Nada de clics en la consola que no queden en código, salvo pasos documentados en el README del módulo.
- **Cuidado con el costo**: nada de recursos con costo por hora sin una decisión (NAT Gateway, Kinesis con shards, RDS, OpenSearch, etc.). Destruye tus stages de prueba al terminar.

---

## 8. Estructura del repo

```
/AGENTS.md            ← este archivo (reglas)
/CLAUDE.md, /GEMINI.md← punteros a este archivo para cada herramienta
/contracts/           ← esquemas JSON compartidos + ejemplos
/docs/
  reto.md             ← enunciado y rúbrica
  arquitectura.md     ← diseño + inventario de recursos
  mapa-dolores.md     ← dolores del cliente → solución → estado
  bitacora/           ← un archivo por sesión de trabajo
  decisiones/         ← un archivo por decisión
/services/            ← backend (un subdirectorio por servicio o dominio)
/workflows/           ← definiciones de Step Functions
/frontend/            ← portal de usuario y panel de operador
/analytics/           ← exportación y dashboards (2.ª nube)
/infra/               ← IaC compartida (si aplica)
/scripts/             ← utilidades (simuladores, carga, estado)
/.claude/commands/    ← comandos de Claude Code (/sync, /tomar, /ayuda, /atender, /cerrar)
```

Las carpetas vacías se crean cuando se necesiten. Cada carpeta de módulo debe tener su `README.md`.

---

## 9. Estilo para agentes

- **Pregunta antes de inventar.** Si un dato no está en los contratos, la arquitectura o las decisiones, **no lo asumas en silencio**: deja un `TODO(#issue)` o pregunta.
- **Alcance mínimo**: haz lo que pide la tarea. Nada de refactors ni "mejoras" no solicitadas fuera de tu zona.
- **Código simple y explicable**: hay que defenderlo en un pitch de 5 minutos. Mejor una Lambda clara que una abstracción genérica.
- Comentarios y documentación en **español**; identificadores de código en inglés o español, pero consistentes dentro de cada módulo.
- Toda función nueva debe tener al menos una prueba o un script de verificación reproducible.
- Al terminar, el agente **resume a su humano** qué cambió y qué quedó pendiente, y deja eso mismo en la bitácora.
