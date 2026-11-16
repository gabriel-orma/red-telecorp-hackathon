# Clasificador de reportes por machine learning (local)

Modelo **entrenado por nosotros** que lee el texto libre de un reporte y estima de qué trata: `SIN_INTERNET`, `INTERNET_LENTO`, `SIN_LLAMADAS`, `SIN_SMS`, `SIN_SENAL`, `INTERMITENCIA` u `OTRO` (no es una falla del servicio).

- **Algoritmo:** TF-IDF (palabras, pares de palabras y n-gramas de 3-4 letras, robusto a faltas de ortografía) + **regresión logística multinomial**, entrenada con scikit-learn.
- **Dónde corre:** dentro de la Lambda de registro (`services/base/layer/python/telecorp/ml/triage.py`). La inferencia son sumas y una softmax en Python puro: **sin numpy ni scikit-learn**, **0,2 ms** por reporte y **6 ms** de carga del modelo (329 KB). El texto **nunca sale de AWS**.
- **Para qué sirve:** un reporte de tipo `OTRO` solo suma al conteo de un incidente colectivo (regla de los 10 usuarios) si el modelo lo clasifica como problema del servicio con confianza ≥ 0,5 y un tipo del catálogo («el modelo solo suma»: nunca resta reportes que las reglas ya cuentan; ver `reglas.triage_ia_confirma_servicio`). Si el modelo no está disponible, cae a las reglas y lo dice (`fuente: "REGLAS"`); **nunca se presenta como ML algo que no lo es**.

## Datos (sintéticos: es la limitación principal)
No tenemos reportes reales de clientes, así que los textos son **sintéticos**, redactados por modelos de lenguaje que trabajaron por separado y sin verse entre sí:

| Conjunto | Textos | Autor | Uso |
|---|---|---|---|
| `datos/entrenamiento.csv` | 770 (70+40 por clase) | A y A2 | entrenar y elegir hiperparámetros (validación cruzada) |
| `datos/validacion.csv` | 245 (35 por clase) | B (estilo exigente) | decidir qué mejorar durante el desarrollo |
| `datos/prueba.csv` | 245 (35 por clase) | C (mensajes largos de chat y notas de voz, sin frases obvias) | **medido una sola vez** al terminar |

Sin fuga: ningún texto se repite entre conjuntos; vocabulario, IDF e hiperparámetros salen solo del entrenamiento (el IDF se recalcula dentro de cada pliegue); el umbral de confianza se eligió con predicciones fuera de pliegue del entrenamiento; la prueba no influyó en ningún parámetro. Los hashes de los datos están en `resultados.json` y dentro del modelo (una prueba falla si el modelo y los datos no coinciden).

**Transparencia del proceso:** la primera versión se entrenó con 490 textos y se evaluó con el conjunto B (exactitud 0,825, `SIN_INTERNET` con recall 0,57). Como ya había visto esa evaluación, **dejó de ser prueba**: pasó a ser *validación*, se añadieron 280 textos de entrenamiento más variados y se pidió una prueba nueva (C), medida una sola vez.

## Resultados (`resultados.json`, 245 textos de la prueba final)
| Modelo | Exactitud | F1 macro |
|---|---|---|
| **Regresión logística (el modelo en producción)** | **0,935** (IC 95 %: 0,902–0,963) | **0,935** |
| Naive Bayes (complemento) | 0,894 | 0,893 |
| Reglas de palabras clave (escritas antes de ver los datos) | 0,404 | 0,414 |
| Clase mayoritaria | 0,143 | — |

Por clase (F1): SIN_INTERNET 0,94 · INTERNET_LENTO 0,96 · SIN_LLAMADAS 0,90 · SIN_SMS 0,97 · SIN_SENAL 0,93 · INTERMITENCIA 0,93 · OTRO 0,91. El error más frecuente: `SIN_SENAL` confundido con `SIN_LLAMADAS` (3 de 35).

**La decisión que importa** (¿suma al conteo del colectivo?), con el umbral 0,5: en la prueba suman 179 reportes y el **99,4 %** son realmente del servicio (97,2 % con la clase exacta), con una cobertura del 84,8 % de los reportes de servicio. En la validación: 100 % y 81,4 %.

## Límites (léelos antes de citar las cifras)
- Las cifras miden la capacidad de **generalizar entre estilos de escritura sintéticos**, no la precisión que tendrá con clientes reales, cuya forma de escribir no conocemos. Esperamos que baje con texto real.
- Los conjuntos tienen 35 textos por clase: los intervalos son anchos (IC 95 % de ±3 puntos en el total, bastante más por clase).
- La prueba tiene textos largos (mediana de 34 palabras) y la validación más cortos; que la prueba salga mejor que la validación se explica probablemente por más evidencia por texto, no porque el modelo sea mejor de lo que parece.
- Solo conoce 7 clases. Un tipo nuevo exige datos nuevos y reentrenar.
- La validación cruzada del entrenamiento (F1 0,92) es optimista porque comparte autor; no se usa como cifra de calidad.

## Comparación con Gemini (IA generativa, opcional)
| | ML local (este modelo) | Gemini (nivel gratuito) |
|---|---|---|
| Exactitud | **0,935 medida** en la prueba | **No medida**: no tuvimos la clave. No se afirma ninguna cifra |
| Costo | 0 | 0 mientras se respeten las cuotas (10/min, 60/h por defecto en el código) |
| Latencia | 0,2 ms | segundos (red + modelo) |
| Privacidad | el texto no sale de AWS | el texto (enmascarado) saldría a Google; el nivel gratuito puede usar el contenido para mejorar sus productos → **apagado por defecto** (`triageTexto`) |
| Determinismo | total (mismo texto, mismo resultado) | no |
| Cobertura de casos raros | solo lo visto en el entrenamiento | amplia (cero ejemplos) |
| Dependencias | ninguna | clave, red, cuota |
| Tiempo para tenerlo | ~2 h (datos, entrenamiento, evaluación) | ~1 h (integración) pero bloqueado por la clave |

Gemini **sigue disponible** para el *análisis del incidente* (agregados, sin datos personales) y, si se activa expresamente, para el triage del texto libre. Para el triage de texto, el modelo local es la opción por defecto.

## Comparación con embeddings preentrenados (conservamos el modelo actual)
Se midieron `paraphrase-multilingual-MiniLM-L12-v2` y `multilingual-e5-small` (embeddings + regresión logística) contra este clasificador en una **prueba nueva y a ciegas** (280 textos de un autor distinto): ninguno mejora el F1 macro (0,947 contra 0,875 y 0,911), ambos cometen más falsos positivos del conteo de colectivos y ninguno cabe en los 250 MB de una capa de Lambda. Protocolo, tablas, costos y límites: [`comparacion/README.md`](comparacion/README.md).

## Reentrenar
```bash
pip install scikit-learn
python ml/triage/entrenar.py                 # entrena, valida con validacion.csv y regenera triage_modelo.json y resultados.json
python ml/triage/entrenar.py --prueba-final  # SOLO al terminar el desarrollo; se niega a repetirse (usa --forzar con una prueba nueva)
pytest services/base/tests/test_ml_triage.py
```
Si cambias `datos/entrenamiento.csv`, hay que reentrenar: una prueba falla si el modelo y los datos no coinciden. Tras reentrenar, actualiza `UMBRAL_CONFIANZA_TRIAGE_ML` en `reglas.py` si el umbral cambió (otra prueba lo comprueba).
