# Comparación del triage ML con embeddings preentrenados

- **Autor**: rodrigo (+ Claude Code)
- **Fecha**: 2026-11-15
- **Issue / PR**: PR a `main` (solo documentación y script de medición; no cambia el modelo de producción)
- **Rama**: `docs/rod-ml-comparacion`

## Qué se hizo
- Se comparó el clasificador de producción (TF-IDF + regresión logística) con `paraphrase-multilingual-MiniLM-L12-v2` y `multilingual-e5-small` (embeddings congelados en ONNX int8 + regresión logística), con los mismos datos, pliegues, semilla y regla de umbral.
- Protocolo sin fuga: modelos, hiperparámetros y regla de decisión se congelan **antes** de abrir la prueba nueva (280 textos de un autor distinto, 0 repetidos con los conjuntos anteriores), que se mide una sola vez.
- **Resultado**: se conserva el modelo actual (F1 macro 0,947 contra 0,875 y 0,911; 2 falsos positivos del conteo contra 4 y 5; ninguno cabe en 250 MB de una capa de Lambda: 259 y 267 MB contra 0,3 MB).

## Archivos tocados
`ml/triage/comparacion/` (script, requisitos, `resultados.json`, `congelado.json`, datos de la prueba nueva, README) y un párrafo en `ml/triage/README.md`.

## Cómo probarlo
`python ml/triage/comparacion/comparar.py todo --prueba-nueva ml/triage/comparacion/datos/prueba_nueva.csv` (descarga ~230 MB de pesos ONNX a `HF_HOME`, fuera del repo; sin credenciales ni costo).

## Decisiones tomadas
- No reemplazar el modelo de producción: la regla de decisión (mejora ≥ 0,03 con IC que excluya 0, no más falsos positivos, cabe en Lambda) no se cumple.

## Pendiente / siguiente paso
- Todo el texto es sintético: si se reúnen reportes reales etiquetados, volver a correr la comparación.
- Los pesos fp32 no se evaluaron (no caben en Lambda); el tercer candidato propuesto (`potion-multilingual-128M`) solo se verificó por la API.
