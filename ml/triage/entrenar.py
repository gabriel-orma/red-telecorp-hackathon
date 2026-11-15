"""Entrena y EVALÚA el clasificador de reportes (TF-IDF + regresión logística) y exporta el modelo para la Lambda.

    pip install scikit-learn
    python ml/triage/entrenar.py                  # entrena, valida y genera resultados.json + triage_modelo.json
    python ml/triage/entrenar.py --prueba-final   # además mide el conjunto de PRUEBA (una sola vez, al terminar el desarrollo)

Protocolo (pensado para NO filtrar información de la evaluación al entrenamiento):
  1. Tres conjuntos de textos sintéticos redactados por autores distintos que no se vieron entre sí:
     `entrenamiento.csv`, `validacion.csv` (se usa durante el desarrollo) y `prueba.csv` (reservado: se mide una sola vez).
     Se eliminan de validación y prueba los textos que, normalizados, ya estén en otro conjunto.
  2. Vocabulario, IDF e hiperparámetros se obtienen SOLO con el entrenamiento (validación cruzada estratificada de 5 pliegues; el
     IDF se recalcula dentro de cada pliegue).
  3. El umbral de confianza con el que un reporte `OTRO` puede sumar al conteo de un colectivo se elige con las predicciones fuera de
     pliegue del ENTRENAMIENTO (nunca con validación ni prueba).
  4. La validación sirve para decidir qué mejorar; la PRUEBA se mide al final, con el modelo ya fijado, y no se ajusta nada después.
  5. Se comparan líneas base: clase mayoritaria, reglas de palabras clave escritas antes de ver los datos de evaluación, y Naive Bayes.
"""
import csv
import hashlib
import json
import math
import pathlib
import platform
import re
import sys

import numpy as np
import scipy.sparse as sp
import sklearn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.model_selection import StratifiedKFold
from sklearn.naive_bayes import ComplementNB

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ / "services" / "base" / "layer" / "python"))
from telecorp.ml import triage  # noqa: E402  (el MISMO vectorizador que usa la Lambda)

CLASES = ["SIN_INTERNET", "INTERNET_LENTO", "SIN_LLAMADAS", "SIN_SMS", "SIN_SENAL", "INTERMITENCIA", "OTRO"]
SEMILLA = 20261114
MIN_DF = 3
PISO_UMBRAL = 0.50
GRID_C = [0.3, 1.0, 3.0, 10.0, 30.0]
GRID_ALFA = [0.1, 0.3, 1.0]
MODELO_SALIDA = RAIZ / "services" / "base" / "layer" / "python" / "telecorp" / "ml" / "triage_modelo.json"
VERSION = "tfidf-lr-v1"


def leer(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        filas = [(r["texto"].strip(), r["etiqueta"].strip()) for r in csv.DictReader(f)]
    malas = [e for _, e in filas if e not in CLASES]
    assert not malas, f"etiquetas desconocidas: {set(malas)}"
    return filas


def sha(ruta):
    return hashlib.sha256(pathlib.Path(ruta).read_bytes()).hexdigest()[:16]


# ---------------------------------------------------------------- Vectorización (usa el código de la Lambda)
def ajustar_vocabulario(textos):
    """Vocabulario (df ≥ MIN_DF) e IDF suavizado, calculados SOLO con `textos`."""
    n, df = len(textos), {}
    for t in textos:
        for k in triage.caracteristicas(t):
            df[k] = df.get(k, 0) + 1
    vocab = sorted(k for k, d in df.items() if d >= MIN_DF)
    idf = {k: math.log((1 + n) / (1 + df[k])) + 1.0 for k in vocab}
    return vocab, idf


def matriz(textos, vocab, idf):
    indice = {k: i for i, k in enumerate(vocab)}
    filas, cols, vals = [], [], []
    for r, t in enumerate(textos):
        for k, x in triage.vectorizar(triage.caracteristicas(t), idf).items():
            filas.append(r), cols.append(indice[k]), vals.append(x)
    return sp.csr_matrix((vals, (filas, cols)), shape=(len(textos), len(vocab)))


def ajustar_lr(textos, y, c):
    vocab, idf = ajustar_vocabulario(textos)
    modelo = LogisticRegression(C=c, max_iter=2000, random_state=SEMILLA)
    modelo.fit(matriz(textos, vocab, idf), y)
    return vocab, idf, modelo


def probs_lr(vocab, idf, modelo, textos):
    p = modelo.predict_proba(matriz(textos, vocab, idf))
    salida = np.zeros((len(textos), len(CLASES)))
    for j, c in enumerate(modelo.classes_):
        salida[:, CLASES.index(c)] = p[:, j]
    return salida


def predecir_nb(textos_ent, y, alfa, textos):
    vocab, idf = ajustar_vocabulario(textos_ent)
    nb = ComplementNB(alpha=alfa).fit(matriz(textos_ent, vocab, idf), y)
    return nb.predict(matriz(textos, vocab, idf))


# ---------------------------------------------------------------- Línea base de reglas (escrita antes de ver los datos de evaluación)
REGLAS = [  # el primer patrón que coincide manda; si ninguno, OTRO
    ("SIN_SMS", r"\bsms\b|mensajes? de texto|codigos? de verificacion"),
    ("SIN_SENAL", r"sin senal|no tengo senal|no hay senal|sin cobertura|sin barras|solo emergencia|sin servicio"),
    ("SIN_LLAMADAS", r"llamad|no puedo llamar|no puedo hacer llamadas"),
    ("INTERMITENCIA", r"intermit|se corta|va y viene|se cae|cada rato|a ratos|inestable|se va y"),
    ("INTERNET_LENTO", r"lent[oa]|demora|\blag\b|se traba|se congela|poca velocidad|velocidad"),
    ("SIN_INTERNET", r"sin internet|no hay internet|no tengo internet|no navega|sin conexion|no carga|se cayo el internet|sin datos"),
]


def reglas_palabras(texto):
    t = triage.normalizar(texto)
    for clase, patron in REGLAS:
        if re.search(patron, t):
            return clase
    return "OTRO"


# ---------------------------------------------------------------- Métricas
def metricas(y_real, y_pred):
    p, r, f, s = precision_recall_fscore_support(y_real, y_pred, labels=CLASES, zero_division=0)
    return {"exactitud": round(accuracy_score(y_real, y_pred), 4),
            "f1_macro": round(f1_score(y_real, y_pred, labels=CLASES, average="macro", zero_division=0), 4),
            "por_clase": {c: {"precision": round(p[i], 3), "recall": round(r[i], 3), "f1": round(f[i], 3), "n": int(s[i])} for i, c in enumerate(CLASES)}}


def intervalo_bootstrap(y_real, y_pred, funcion, n=1000):
    rng = np.random.default_rng(SEMILLA)
    y_real, y_pred = np.array(y_real), np.array(y_pred)
    valores = []
    for _ in range(n):
        i = rng.integers(0, len(y_real), len(y_real))
        valores.append(funcion(y_real[i], y_pred[i]))
    return [round(float(np.percentile(valores, 2.5)), 3), round(float(np.percentile(valores, 97.5)), 3)]


def conteo_servicio(y_real, y_pred, confianza, umbral):
    """Reportes que SUMARÍAN al conteo de un colectivo: se predice una clase de falla con confianza ≥ umbral. Precisión = de ellos,
    cuántos son realmente del servicio (clase real ≠ OTRO) y cuántos además con la clase exacta; cobertura = % de los reportes de
    servicio que suman."""
    y_real, y_pred, confianza = np.array(y_real), np.array(y_pred), np.array(confianza)
    cuenta = (y_pred != "OTRO") & (confianza >= umbral)
    real_servicio = y_real != "OTRO"
    n = int(cuenta.sum())
    return {"umbral": float(umbral), "suman": n,
            "precision_servicio": round(float((cuenta & real_servicio).sum() / n), 4) if n else None,
            "precision_clase_exacta": round(float((cuenta & (y_real == y_pred)).sum() / n), 4) if n else None,
            "cobertura": round(float((cuenta & real_servicio).sum() / max(1, real_servicio.sum())), 4)}


def evaluar(nombre, X, y, X_ent, y_ent, vocab, idf, modelo, mejor_alfa, umbral):
    """Métricas de un conjunto con el modelo YA fijado (regresión logística y líneas base)."""
    p = probs_lr(vocab, idf, modelo, X)
    pred = [CLASES[i] for i in p.argmax(1)]
    pred_nb = list(predecir_nb(X_ent, y_ent, mejor_alfa, X))
    pred_reglas = [reglas_palabras(t) for t in X]
    mayoritaria = max(set(y_ent), key=y_ent.count)

    def f1m(a, b):
        return f1_score(a, b, labels=CLASES, average="macro", zero_division=0)
    return {"nombre": nombre, "n": len(X), "por_clase_n": {c: y.count(c) for c in CLASES},
            "regresion_logistica": {**metricas(y, pred), "intervalo95_exactitud": intervalo_bootstrap(y, pred, accuracy_score),
                                    "intervalo95_f1_macro": intervalo_bootstrap(y, pred, f1m),
                                    "matriz_confusion": {"clases": CLASES, "filas_real_columnas_predicha": confusion_matrix(y, pred, labels=CLASES).tolist()}},
            "naive_bayes_complemento": metricas(y, pred_nb), "reglas_de_palabras": metricas(y, pred_reglas),
            "clase_mayoritaria": {"clase": mayoritaria, "exactitud": round(accuracy_score(y, [mayoritaria] * len(y)), 4)},
            "conteo_con_el_umbral": conteo_servicio(y, pred, p.max(1), umbral)}


def sin_repetidos(filas, vistos):
    """Quita de `filas` lo que ya está en `vistos` (texto normalizado) y lo agrega. Devuelve (filas, cuántas quitó)."""
    salida, quitadas = [], 0
    for t, e in filas:
        n = triage.normalizar(t)
        if n in vistos:
            quitadas += 1
            continue
        vistos.add(n)
        salida.append((t, e))
    return salida, quitadas


def main():
    prueba_final = "--prueba-final" in sys.argv
    ent = leer(AQUI / "datos" / "entrenamiento.csv")
    vistos = {triage.normalizar(t) for t, _ in ent}
    val, rep_val = sin_repetidos(leer(AQUI / "datos" / "validacion.csv"), vistos)
    ruta_prueba = AQUI / "datos" / "prueba.csv"
    prueba, rep_prueba = sin_repetidos(leer(ruta_prueba) if ruta_prueba.exists() else [], vistos)
    if prueba_final and not prueba:
        sys.exit("ERROR: falta datos/prueba.csv")
    X_ent, y_ent = [t for t, _ in ent], [e for _, e in ent]
    print(f"entrenamiento {len(ent)} · validación {len(val)} (quitados {rep_val}) · prueba {len(prueba)} (quitados {rep_prueba})")

    # 1) hiperparámetros SOLO con el entrenamiento (validación cruzada estratificada)
    cv = StratifiedKFold(5, shuffle=True, random_state=SEMILLA)
    resultados_cv, oof_por_c = {}, {}
    for c in GRID_C:
        oof = np.zeros((len(X_ent), len(CLASES)))
        for tr, va in cv.split(X_ent, y_ent):
            vocab, idf, m = ajustar_lr([X_ent[i] for i in tr], [y_ent[i] for i in tr], c)
            oof[va] = probs_lr(vocab, idf, m, [X_ent[i] for i in va])
        pred = [CLASES[i] for i in oof.argmax(1)]
        resultados_cv[c] = round(f1_score(y_ent, pred, labels=CLASES, average="macro"), 4)
        oof_por_c[c] = oof
        print(f"  CV C={c:<5} F1 macro = {resultados_cv[c]}")
    mejor_c = max(GRID_C, key=lambda c: resultados_cv[c])
    oof = oof_por_c[mejor_c]
    alfa_cv = {}
    for a in GRID_ALFA:
        pred = np.empty(len(X_ent), dtype=object)
        for tr, va in cv.split(X_ent, y_ent):
            pred[va] = predecir_nb([X_ent[i] for i in tr], [y_ent[i] for i in tr], a, [X_ent[i] for i in va])
        alfa_cv[a] = round(f1_score(y_ent, list(pred), labels=CLASES, average="macro"), 4)
    mejor_alfa = max(GRID_ALFA, key=lambda a: alfa_cv[a])

    # 2) umbral para sumar al conteo, con las predicciones fuera de pliegue del ENTRENAMIENTO. Regla: el menor umbral ≥ 0,5 (la clase
    #    predicha debe tener más de la mitad de la probabilidad: criterio a priori, no ajustado a ningún conjunto de evaluación) con
    #    precisión ≥ 98 % de «es realmente del servicio» y al menos 50 reportes; si ninguno cumple, el 0,8 de la IA generativa.
    pred_oof = [CLASES[i] for i in oof.argmax(1)]
    conf_oof = oof.max(1)
    umbral = 0.80
    for u in [round(float(x), 2) for x in np.arange(PISO_UMBRAL, 0.96, 0.05)]:
        r = conteo_servicio(y_ent, pred_oof, conf_oof, u)
        if r["suman"] >= 50 and (r["precision_servicio"] or 0) >= 0.98:
            umbral = u
            break
    print(f"mejor C={mejor_c} · umbral elegido con validación cruzada = {umbral}")

    # 3) modelo final con TODO el entrenamiento
    vocab, idf, modelo = ajustar_lr(X_ent, y_ent, mejor_c)
    args = (X_ent, y_ent, vocab, idf, modelo, mejor_alfa, umbral)
    res = {
        "version_modelo": VERSION,
        "datos": {"entrenamiento": {"n": len(ent), "sha256": sha(AQUI / "datos" / "entrenamiento.csv"), "por_clase": {c: y_ent.count(c) for c in CLASES}},
                  "validacion": {"sha256": sha(AQUI / "datos" / "validacion.csv"), "repetidos_eliminados": rep_val},
                  "prueba": {"sha256": sha(ruta_prueba) if ruta_prueba.exists() else None, "repetidos_eliminados": rep_prueba}},
        "configuracion": {"caracteristicas": "palabras + pares de palabras + n-gramas de 3 y 4 letras", "min_df": MIN_DF, "n_caracteristicas": len(vocab),
                          "C_elegido_por_cv": mejor_c, "f1_macro_cv_por_C": {str(k): v for k, v in resultados_cv.items()},
                          "alfa_nb_elegido_por_cv": mejor_alfa, "semilla": SEMILLA,
                          "versiones": {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__}},
        "umbral_para_sumar_al_conteo": {"umbral": umbral, "elegido_con": "predicciones fuera de pliegue del entrenamiento",
                                        "en_validacion_cruzada": conteo_servicio(y_ent, pred_oof, conf_oof, umbral)},
        "validacion": evaluar("validacion (usada durante el desarrollo)", [t for t, _ in val], [e for _, e in val], *args),
    }
    previo = AQUI / "resultados.json"
    if prueba_final and "--forzar" not in sys.argv and previo.exists() and json.loads(previo.read_text(encoding="utf-8")).get("prueba_final", {}).get("n"):
        sys.exit("La prueba final ya se midió con este protocolo (resultados.json). Medirla otra vez la convierte en validación: "
                 "si de verdad hace falta, usa --forzar y escribe un conjunto de prueba NUEVO.")
    if prueba_final:
        res["prueba_final"] = {**evaluar("prueba final (medida una sola vez)", [t for t, _ in prueba], [e for _, e in prueba], *args),
                               "nota": "Medida una vez con el modelo ya fijado; ningún parámetro se ajustó después de verla."}
    elif previo.exists():
        anterior = json.loads(previo.read_text(encoding="utf-8")).get("prueba_final")
        if anterior and anterior.get("n"):
            print("AVISO: resultados.json ya tenía una prueba final; esta ejecución NO la reemplaza ni la mide de nuevo.")
            res["prueba_final"] = anterior
    previo.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4) exportar el modelo (solo lo necesario para inferir en Python puro)
    pesos = modelo.coef_
    orden = [list(modelo.classes_).index(c) for c in CLASES]
    exportado = {"version": VERSION, "clases": CLASES, "umbral_servicio": umbral,
                 "sesgos": [round(float(modelo.intercept_[j]), 5) for j in orden],
                 "vocab": {k: [round(idf[k], 5)] + [round(float(pesos[j][i]), 5) for j in orden] for i, k in enumerate(vocab)
                           if any(abs(pesos[j][i]) > 1e-4 for j in orden)},
                 "entrenado_con": {"n": len(ent), "sha256_datos": sha(AQUI / "datos" / "entrenamiento.csv")}}
    MODELO_SALIDA.write_text(json.dumps(exportado, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"modelo exportado: {MODELO_SALIDA.name} ({MODELO_SALIDA.stat().st_size / 1024:.0f} KB, {len(exportado['vocab'])} características)")

    for clave in ("validacion", "prueba_final"):
        if clave not in res or "regresion_logistica" not in res[clave]:
            continue
        e = res[clave]
        print(f"\n== {e['nombre'].upper()} (n={e['n']}) ==")
        for nombre, k in (("Regresión logística", "regresion_logistica"), ("Naive Bayes", "naive_bayes_complemento"), ("Reglas de palabras", "reglas_de_palabras")):
            print(f"  {nombre:<22} exactitud {e[k]['exactitud']:.3f} · F1 macro {e[k]['f1_macro']:.3f}")
        print(f"  Clase mayoritaria      exactitud {e['clase_mayoritaria']['exactitud']:.3f}")
        print("  IC95 % (bootstrap) LR: exactitud", e["regresion_logistica"]["intervalo95_exactitud"], "· F1 macro", e["regresion_logistica"]["intervalo95_f1_macro"])
        print("  conteo con el umbral:", e["conteo_con_el_umbral"])


if __name__ == "__main__":
    main()
