# Clasificador de reportes por ML local (TF-IDF + regresión logística)

- **Autor**: rodrigo (+ Claude Code)
- **Fecha**: 2026-11-14
- **Issue / PR**: #42 (apilado sobre #40)
- **Rama**: `feat/ml-triage-local`

## Qué se hizo
- Modelo de ML entrenado con scikit-learn y exportado a JSON; la Lambda lo ejecuta en Python puro (0,2 ms, sin dependencias nuevas).
- Triage de los reportes `OTRO`: por defecto lo hace el modelo local (el texto no sale de AWS); Gemini solo si se activa `triageTexto`.
- Protocolo sin fuga con tres conjuntos sintéticos de autores distintos (entrenamiento, validación, prueba medida una sola vez) y comparación con Naive Bayes y con reglas de palabras.

## Archivos y recursos tocados
- Nuevo: `ml/triage/{entrenar.py,README.md,resultados.json,datos/*}`, `services/base/layer/python/telecorp/ml/{triage.py,triage_modelo.json}`, `services/base/tests/test_ml_triage.py`, `docs/decisiones/2026-11-14-ia-ml-local.md`.
- Tocados: `nube2/ia.py` (ruta ML por defecto), `reglas.py` (umbral del modelo), `contracts/schemas/incidencia.schema.json` (`fuente` admite `ML`), `docs/arquitectura.{md,svg}`.

## Cómo probarlo
```bash
pytest services workflows
pip install scikit-learn && python ml/triage/entrenar.py     # reentrena y valida (no mide la prueba final)
```

## Decisiones tomadas
- [D12 · IA del triage](../decisiones/2026-11-14-ia-ml-local.md).

## Pendiente / siguiente paso
- Probar con reportes reales cuando existan (los datos son sintéticos).
- Verificación en la nube del triage ML (pendiente de renovar credenciales del Lab).

## Notas para los otros agentes
- No vuelvas a medir `prueba.csv`: el script se niega (`--forzar` solo con una prueba nueva).
- Si cambias `entrenamiento.csv`, reentrena: una prueba falla si el modelo y los datos no coinciden.
