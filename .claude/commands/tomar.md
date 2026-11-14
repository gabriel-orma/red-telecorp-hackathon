---
description: Reclama una tarea (issue + zona de archivos + rama) sin chocar con los demás
argument-hint: <n° de issue o descripción de la tarea>
---

Quiero empezar a trabajar en: $ARGUMENTS

Sigue AGENTS.md §2, "Antes de empezar una tarea":

1. Primero sincroniza (como en `/sync`, en versión corta: fetch, ponerse al día con `origin/main` y listar issues abiertos).
2. Si $ARGUMENTS es un número, lee ese issue (`gh issue view <n>`). Si no, busca si ya existe un issue similar. Si no existe, **redacta** uno con la plantilla "Tarea" (`.github/ISSUE_TEMPLATE/tarea.yml`) y muéstramelo antes de crearlo con `gh issue create`.
3. Propón la **zona de archivos** (carpetas o archivos concretos) que esta tarea necesita tocar.
4. Compárala con la zona declarada en cada issue `en-progreso`. Si hay superposición, dime con quién chocamos y propón cómo dividir el trabajo o qué pedir por `/ayuda`. **No sigas sin mi OK.**
5. Si no hay choque:
   - `gh issue edit <n> --add-assignee @me --add-label en-progreso`;
   - agrega o actualiza en el cuerpo del issue la sección "Zona de archivos";
   - crea la rama `feat/<n>-<slug>` (o `fix/` o `docs/`) desde `origin/main`.
6. Revisa los `contracts/` y las `docs/decisiones/` relevantes y propón un plan breve antes de escribir código.

Si `gh` no está disponible, dame el texto del issue y los pasos para hacerlo en github.com.
