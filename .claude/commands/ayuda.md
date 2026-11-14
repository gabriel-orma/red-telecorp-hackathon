---
description: Abre un pedido de ayuda para otro agente o persona sin colisionar zonas
argument-hint: <qué necesitas>
---

Necesito ayuda con: $ARGUMENTS

Sigue AGENTS.md §5, "Pedir ayuda":

1. Identifica qué parte de esto **está fuera de mi zona de archivos** (la de mi issue `en-progreso`). Lo que esté dentro de mi zona lo hago yo; no lo delegues.
2. Redacta un issue con la plantilla "Pedido de ayuda" (`.github/ISSUE_TEMPLATE/ayuda.yml`) que incluya:
   - **Qué se necesita**, concreto y verificable (endpoint, función, recurso, con entradas y salidas).
   - **Contrato** de `contracts/` involucrado. Si hace falta uno nuevo, dilo explícitamente: eso requiere además un issue `contrato`.
   - **Zona de archivos sugerida** para quien lo tome. Debe **no cruzarse** con mi zona ni con otras `en-progreso`.
   - **Qué hago yo mientras tanto** (normalmente, un mock que cumple el contrato).
   - **Urgencia**: ¿me bloquea? Si sí, agrega el label `bloqueado`.
   - Un enlace a mi issue o rama.
3. Muéstrame el texto. Con mi OK, créalo: `gh issue create --label ayuda ...`.
4. Si estoy esperando, implementa el mock en mi zona y deja `TODO(#<n° del issue de ayuda>)` donde haya que reemplazarlo.
