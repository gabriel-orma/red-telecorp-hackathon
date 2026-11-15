"""Clasificador de reportes por *machine learning* local: TF-IDF + regresión logística multinomial.

Qué hace: dado el texto libre de un reporte, estima de qué trata (SIN_INTERNET, INTERNET_LENTO, SIN_LLAMADAS, SIN_SMS,
SIN_SENAL, INTERMITENCIA u OTRO = no es una falla del servicio) y con qué probabilidad.

Por qué local: el texto NUNCA sale de AWS (no se envía a ninguna API de IA externa), cuesta cero, responde en milisegundos y es
determinista. El modelo se ENTRENA fuera de la Lambda (`ml/triage/entrenar.py`, scikit-learn) y aquí solo se EJECUTA:
la inferencia son sumas y una softmax en Python puro, sin numpy ni scikit-learn.

El vectorizador de este archivo es el MISMO que usa el entrenamiento: así no hay desajuste entre entrenar y predecir.
Honestidad: el modelo se entrenó con textos sintéticos (no hay reportes reales), ver `ml/triage/README.md` para métricas y límites.
"""
import json
import math
import os
import re
import unicodedata

RUTA_MODELO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "triage_modelo.json")
MAX_CARACTERES = 2000          # igual que el límite de la descripción del reporte
_NO_ALFANUM = re.compile(r"[^a-z0-9]+")
_REPETIDOS = re.compile(r"(.)\1{2,}")
_modelo = None


# ---------------------------------------------------------------- Vectorizador (compartido con el entrenamiento)
def normalizar(texto) -> str:
    """Minúsculas, sin tildes (ñ→n), letras repetidas reducidas a 2 («nooo»→«noo»), solo [a-z0-9] separado por espacios."""
    s = unicodedata.normalize("NFKD", str(texto or "")[:MAX_CARACTERES].lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _NO_ALFANUM.sub(" ", _REPETIDOS.sub(r"\1\1", s)).strip()


def caracteristicas(texto) -> dict:
    """Conteos de: palabras (w:), pares de palabras (b:) y n-gramas de 3 y 4 letras dentro de cada palabra (c:, robustos a faltas)."""
    palabras = normalizar(texto).split()
    cuentas: dict = {}

    def sumar(clave):
        cuentas[clave] = cuentas.get(clave, 0) + 1
    for p in palabras:
        sumar("w:" + p)
    for a, b in zip(palabras, palabras[1:]):
        sumar(f"b:{a}_{b}")
    for p in palabras:
        marco = f" {p} "
        for n in (3, 4):
            for i in range(len(marco) - n + 1):
                sumar("c:" + marco[i:i + n])
    return cuentas


def vectorizar(cuentas: dict, idf: dict) -> dict:
    """TF sublineal (1+ln c) × IDF, normalizado a longitud 1 (L2). Solo las características que el modelo conoce."""
    v = {k: (1.0 + math.log(c)) * idf[k] for k, c in cuentas.items() if k in idf}
    norma = math.sqrt(sum(x * x for x in v.values()))
    return {k: x / norma for k, x in v.items()} if norma > 0 else {}


# ---------------------------------------------------------------- Inferencia
def cargar_modelo(ruta: str | None = None) -> dict | None:
    """Modelo exportado por `entrenar.py` (JSON). None si no existe: el sistema cae a las reglas (nunca finge ML)."""
    global _modelo
    if ruta is None and _modelo is not None:
        return _modelo
    try:
        with open(ruta or RUTA_MODELO, encoding="utf-8") as f:
            m = json.load(f)
        if ruta is None:
            _modelo = m
        return m
    except (OSError, ValueError):
        return None


def clasificar(texto, modelo: dict | None = None) -> dict | None:
    """{clase, confianza, probabilidades, modelo} o None si no hay modelo. Con un texto sin ninguna característica conocida
    devuelve OTRO con confianza 0 (no hay evidencia: nunca se inventa una clase de falla)."""
    m = modelo or cargar_modelo()
    if not m:
        return None
    clases = m["clases"]
    vocab = m["vocab"]                                            # {característica: [idf, peso_clase_0, …, peso_clase_k]}
    cuentas = caracteristicas(texto)
    v = vectorizar(cuentas, {k: vocab[k][0] for k in cuentas if k in vocab})
    if not v:
        return {"clase": "OTRO", "confianza": 0.0, "probabilidades": {c: 0.0 for c in clases}, "modelo": m["version"]}
    z = list(m["sesgos"])
    for k, x in v.items():
        for i, w in enumerate(vocab[k][1:]):
            z[i] += w * x
    mayor = max(z)
    e = [math.exp(s - mayor) for s in z]
    total = sum(e)
    p = [x / total for x in e]
    i = max(range(len(p)), key=lambda j: p[j])
    return {"clase": clases[i], "confianza": round(p[i], 4), "probabilidades": {c: round(x, 4) for c, x in zip(clases, p)},
            "modelo": m["version"]}
