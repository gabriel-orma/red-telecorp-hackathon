# Comparación: TF-IDF + regresión logística (producción) vs embeddings preentrenados

**Veredicto: se conserva el modelo actual.** Ninguno de los dos candidatos lo mejora en una prueba nueva y a ciegas, y ninguno cabe en el límite de 250 MB de una capa de Lambda con las dependencias necesarias.

## Qué se comparó
| | Modelo | Licencia | Cómo se usó |
|---|---|---|---|
| **base** | TF-IDF (palabras, bigramas, caracteres 3–4) + regresión logística multinomial (`ml/triage/entrenar.py`) | propia | el código de producción, sin cambios |
| minilm | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (118 M parámetros, 384 dim) | Apache-2.0 | embeddings congelados (ONNX int8) + regresión logística |
| e5small | `intfloat/multilingual-e5-small` (118 M parámetros, 384 dim, prefijo `query: `) | MIT | ídem |

Mismos datos de entrenamiento (770), mismos pliegues, misma semilla y la misma regla de umbral (0,5, elegido por validación cruzada) para los tres. Los embeddings se calcularon con la variante **ONNX int8**, que es la única forma realizable en Lambda; los pesos fp32 (471 MB cada uno) **no se evaluaron** y esa variante no cabría de todos modos (ver «Costos»).

## Protocolo sin fuga
1. `congelar` fija modelos, hiperparámetros, umbrales y la huella de los coeficientes **antes** de abrir la prueba nueva (`congelado.json`).
2. `medir` abre la prueba nueva **una sola vez** y aborta si los ajustes recalculados no coinciden con lo congelado.
3. La regla de decisión también se fijó antes: reemplazar solo si (i) el F1 macro mejora ≥ 0,03 con intervalo bootstrap pareado (1000) que excluya 0, (ii) no hay más falsos positivos del conteo binario ni menor precisión de servicio, (iii) cabe en Lambda (≤ 250 MB, ≤ 1 GB de memoria, arranque ≤ 5 s) y (iv) licencia permisiva.
4. La prueba nueva (`datos/prueba_nueva.csv`, 280 textos: 40 por clase, perfiles normal / negación / faltas de ortografía / peruanismos / voz imperfecta / ambiguos) la escribió un autor distinto de los de entrenamiento, validación y la prueba anterior; **0 textos repetidos** con esos conjuntos. La validación y la prueba antiguas ya se usaron para desarrollar el modelo de producción: se reportan solo como referencia («ya vistas»).

## Resultados en la prueba nueva (n = 280)
| | exactitud | F1 macro [IC 95 %] | diferencia de F1 vs base [IC 95 %] | falsos positivos / 40 `OTRO` | precisión «es servicio» | cobertura |
|---|---|---|---|---|---|---|
| **base (producción)** | **0,946** | **0,947** [0,916–0,971] | — | **2** | **0,991** | 0,946 |
| minilm int8 | 0,875 | 0,875 [0,836–0,912] | −0,071 [−0,114; −0,031] | 4 | 0,982 | 0,900 |
| e5small int8 | 0,911 | 0,911 [0,872–0,942] | −0,036 [−0,071; −0,002] | 5 | 0,978 | 0,946 |

Un «falso positivo» es un reporte `OTRO` (no relacionado con el servicio) que el modelo manda a la cuenta de un colectivo: es el error que más daño hace, porque podría disparar un colectivo falso. El modelo actual es el que menos comete.

Exactitud por perfil (base / minilm / e5small): normal 1,00 / 0,93 / 0,98 · negación 0,91 / 0,84 / 0,84 · faltas 0,95 / 0,77 / 0,91 · peruanismos 0,95 / 0,91 / 0,86 · voz 0,96 / 0,89 / 0,96 · ambiguos 0,89 / 0,96 / 0,96. Los embeddings solo ganan en textos ambiguos; el detalle por clase y las matrices de confusión están en `resultados.json`.

## Costos (proxy medido en una CPU de portátil con 2 hilos, no en AWS)
| | arranque | latencia mediana | memoria pico | artefacto |
|---|---|---|---|---|
| base | 0,01 s | 0,22 ms | 23 MB | 329 KB (JSON) + 4 KB de código, **sin dependencias** |
| minilm int8 | 1,25 s | 6,5 ms | 441 MB | 113 MB modelo + 9 MB tokenizador + 137 MB de onnxruntime/numpy/tokenizers = **259 MB** |
| e5small int8 | 1,12 s | 7,2 ms | 447 MB | 113 + 16 + 137 = **267 MB** |

Con torch y los pesos fp32 el paquete supera los 984 MB. Los dos candidatos quedan **por encima de los 250 MB** de una capa de Lambda y cuestan ~20× más memoria y ~30× más latencia, para un resultado peor.

## Conclusión y límites
- Producción **sin cambios**: el clasificador TF-IDF + regresión logística sigue siendo el mejor en exactitud, en falsos positivos del conteo y en costo, y no añade dependencias.
- Todos los textos son **sintéticos**: la prueba mide generalización entre autores, no desempeño con clientes reales (no hay datos reales). El orden de los modelos podría cambiar con texto real; si algún día se reúnen reportes reales etiquetados, `comparar.py` se vuelve a correr tal cual.
- No se probó un tercer candidato (`minishlab/potion-multilingual-128M`, MIT): solo se verificó por la API de Hugging Face; está en `resultados.json` como «no evaluado».
- El ML nunca sustituye controles deterministas: el modelo solo **suma** reportes `OTRO` al conteo (`reglas.triage_ia_confirma_servicio`); la regla de los 10 usuarios y sus ventanas no cambian.

## Reproducir
```bash
pip install -r ml/triage/comparacion/requisitos.txt     # torch solo para --fp32; no es necesario
python ml/triage/comparacion/comparar.py todo --prueba-nueva <ruta a prueba_nueva.csv>
```
Los pesos se descargan con `huggingface_hub` a `HF_HOME` (fuera del repo) la primera vez; no usa credenciales ni servicios de pago.
