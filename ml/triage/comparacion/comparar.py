"""Comparación REPRODUCIBLE: clasificador de producción (TF-IDF + regresión logística) vs embeddings preentrenados congelados + regresión logística.

Candidatos: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 y intfloat/multilingual-e5-small (prefijo «query: »).
Misma tarea, mismos datos (entrenamiento.csv, 770), mismos pliegues, misma semilla, mismas reglas de umbral que `ml/triage/entrenar.py`
(que se IMPORTA, no se modifica). Dependencias (ver requisitos.txt): scikit-learn, numpy, scipy, torch (CPU), sentence-transformers,
onnxruntime, tokenizers, huggingface_hub. Este script no instala nada. Los modelos se descargan con huggingface_hub al HF_HOME
(fuera del repo) la primera vez; no usa credenciales ni servicios de pago.

    python comparar.py comprobar                      # tabla previa (API pública de HF; no descarga pesos)
    python comparar.py congelar                       # embeddings + CV (solo entrenamiento) + umbrales -> congelado.json. NO lee la prueba nueva
    python comparar.py medir [--prueba-nueva RUTA]    # UNA medición en la prueba nueva -> resultados.json y datos/prueba_nueva.csv
    python comparar.py costos                         # arranque, latencia, memoria, tamaños (subprocesos aislados; proxy de esta CPU)
    python comparar.py todo [--prueba-nueva RUTA]     # comprobar + congelar + medir + costos

Protocolo sin fuga: la prueba nueva solo se abre en `medir`, después de escribir congelado.json (modelos, C, umbrales y huella de los
coeficientes). `medir` recalcula los ajustes y aborta si no coinciden con lo congelado. Validación y prueba antiguas ya se usaron para
desarrollar el modelo de producción: se reportan solo como referencia «ya vista».
"""
import argparse
import csv
import gc
import hashlib
import io
import json
import os
import pathlib
import platform
import subprocess
import sys
import time

AQUI = pathlib.Path(__file__).resolve().parent
TRIAGE = AQUI.parent
RAIZ = TRIAGE.parents[1]
RESULTADOS = AQUI / "resultados.json"
CONGELADO = AQUI / "congelado.json"
DATOS_PN = AQUI / "datos" / "prueba_nueva.csv"
PRUEBA_NUEVA_DEFECTO = RAIZ.parent / "ml" / "datos" / "prueba_nueva_autorD.csv"  # lab/ml/datos (fuera del repo)
SEMILLA = 20261114
N_BOOT = 1000
GRID_C_EMB = [0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0]  # embeddings L2-normalizados: C más grande que en TF-IDF
PERFILES = ["normal", "negacion", "faltas", "peruanismo", "voz", "ambiguo"]
HILOS_LAMBDA = 2     # vCPU aproximadas de una Lambda con ~1,5-3 GB; proxy

MODELOS = {
    "minilm": dict(hf="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", rev="e8f8c211226b894fcb81acc59f3b34ba3efd5f42", prefijo="",
                   max_len=128, licencia="apache-2.0", int8="onnx/model_qint8_avx512_vnni.onnx",
                   archivos=["config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "sentencepiece.bpe.model", "modules.json",
                             "sentence_bert_config.json", "1_Pooling/config.json", "config_sentence_transformers.json"]),
    "e5small": dict(hf="intfloat/multilingual-e5-small", rev="614241f622f53c4eeff9890bdc4f31cfecc418b3", prefijo="query: ",
                    max_len=128, licencia="mit", int8="onnx/model_qint8_avx512_vnni.onnx",
                    archivos=["config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "sentencepiece.bpe.model", "modules.json",
                              "sentence_bert_config.json", "1_Pooling/config.json"]),
}
# Tercer candidato PROPUESTO: solo se comprueba por la API (no se evaluó por el límite de tiempo)
PROPUESTO = {"potion": "minishlab/potion-multilingual-128M"}
REGLA = {
    "i": "F1 macro del candidato supera al de la línea base por >= 0,03 y el IC bootstrap pareado (1000) de la diferencia excluye 0",
    "ii": "falsos positivos del conteo binario <= los de la línea base Y precisión de servicio >= la de la línea base",
    "iii": "viable en Lambda: paquete (código+dependencias+modelo) <= 250 MB descomprimidos, memoria estimada <= 1024 MB, arranque en frío <= 5 s (proxy), sin GPU ni pago",
    "iv": "licencia permisiva (Apache-2.0/MIT)",
    "lectura": "(i) y (ii) se evalúan con los embeddings fp32 (lo congelado); (iii) se juzga con la forma realizable más pequeña (ONNX int8), cuyas "
              "métricas se reportan aparte como comprobación de implementabilidad. Si no se cumple TODO: conservar el modelo actual.",
}


# ============================================================================ utilidades
def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_archivo(ruta):
    return sha256_bytes(pathlib.Path(ruta).read_bytes())


def leer_json(ruta):
    return json.loads(pathlib.Path(ruta).read_text(encoding="utf-8")) if pathlib.Path(ruta).exists() else {}


def guardar(clave, valor):
    r = leer_json(RESULTADOS)
    r[clave] = valor
    RESULTADOS.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")


def ruta_modelo(clave, fp32=False):
    """Carpeta local de la revisión fijada. Si faltan archivos, se bajan con huggingface_hub (reanudable); si no, no se toca la red."""
    cfg = MODELOS[clave]
    hf_home = pathlib.Path(os.environ.get("HF_HOME", pathlib.Path.home() / ".cache" / "huggingface"))
    carpeta = hf_home / "hub" / ("models--" + cfg["hf"].replace("/", "--")) / "snapshots" / cfg["rev"]
    faltan = [f for f in cfg["archivos"] + [cfg["int8"]] + (["model.safetensors"] if fp32 else []) if not (carpeta / f).exists()]
    if faltan:
        from huggingface_hub import hf_hub_download
        for f in faltan:
            hf_hub_download(cfg["hf"], f, revision=cfg["rev"])
    return carpeta


def mem_mb():
    """(memoria actual, pico) del proceso en MB; sin dependencias externas."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        k, p = ctypes.windll.kernel32, ctypes.windll.psapi
        k.GetCurrentProcess.restype = wintypes.HANDLE
        p.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        pmc = PMC()
        pmc.cb = ctypes.sizeof(pmc)
        p.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
        return pmc.WorkingSetSize / 2 ** 20, pmc.PeakWorkingSetSize / 2 ** 20
    import resource
    pico = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return pico, pico


# ============================================================================ trabajadores (subprocesos: aíslan memoria)
class EmbedORT:
    """Inferencia SIN torch: tokenizers + onnxruntime + numpy (la forma que cabría en una capa de Lambda)."""

    def __init__(self, clave, hilos):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np, cfg, base = np, MODELOS[clave], ruta_modelo(clave)
        so = ort.SessionOptions()
        so.intra_op_num_threads, so.inter_op_num_threads = hilos, 1
        self.s = ort.InferenceSession(str(base / cfg["int8"]), so, providers=["CPUExecutionProvider"])
        self.entradas = {i.name for i in self.s.get_inputs()}
        self.salida = self.s.get_outputs()[0].name
        self.tok = Tokenizer.from_file(str(base / "tokenizer.json"))
        self.tok.enable_truncation(cfg["max_len"])
        self.tok.enable_padding(pad_id=1, pad_token="<pad>")
        self.prefijo = cfg["prefijo"]

    def __call__(self, textos):
        np = self.np
        enc = self.tok.encode_batch([self.prefijo + t for t in textos])
        ids = np.array([e.ids for e in enc], dtype=np.int64)
        mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self.entradas:
            feeds["token_type_ids"] = np.zeros_like(ids)
        h = self.s.run([self.salida], feeds)[0]
        m = mask[..., None].astype(h.dtype)
        v = (h * m).sum(1) / np.maximum(m.sum(1), 1e-9)
        return (v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)).astype(np.float32)


def trabajador_embed(clave, variante, entrada, salida):
    import numpy as np
    conjuntos = json.loads(pathlib.Path(entrada).read_text(encoding="utf-8"))
    cfg, out, meta = MODELOS[clave], {}, {}
    if variante == "fp32":
        import torch
        from sentence_transformers import SentenceTransformer
        torch.manual_seed(SEMILLA)
        m = SentenceTransformer(str(ruta_modelo(clave, True)), device="cpu")
        m.max_seq_length = cfg["max_len"]
        meta["versiones"] = {"torch": torch.__version__, "sentence_transformers": __import__("sentence_transformers").__version__}
        for nombre, textos in conjuntos.items():
            pref = [cfg["prefijo"] + t for t in textos]
            out[nombre] = m.encode(pref, batch_size=32, convert_to_numpy=True, normalize_embeddings=True).astype(np.float32)
            largos = [len(x) for x in m.tokenizer(pref, add_special_tokens=True)["input_ids"]]
            meta[nombre] = {"tokens_max": max(largos), "tokens_mediana": float(np.median(largos)), "truncados": int(sum(x > cfg["max_len"] for x in largos))}
    else:
        import onnxruntime
        e = EmbedORT(clave, 4)
        meta["versiones"] = {"onnxruntime": onnxruntime.__version__}
        for nombre, textos in conjuntos.items():
            out[nombre] = np.concatenate([e(textos[i:i + 32]) for i in range(0, len(textos), 32)])
    np.savez(salida, **out)
    pathlib.Path(str(salida) + ".json").write_text(json.dumps(meta), encoding="utf-8")


def trabajador_costo(variante, hilos, n):
    """Mide en un proceso limpio: importaciones, carga, primera inferencia, latencia por texto y memoria pico."""
    t0 = time.perf_counter()
    with open(TRIAGE / "datos" / "validacion.csv", encoding="utf-8", newline="") as f:   # textos ya vistos: no son la prueba nueva
        textos = [r["texto"].strip() for r in csv.DictReader(f)][:n]
    if variante == "base":
        sys.path.insert(0, str(RAIZ / "services" / "base" / "layer" / "python"))
        from telecorp.ml import triage
        t1 = time.perf_counter()
        modelo = triage.cargar_modelo()
        t2 = time.perf_counter()
        infer = lambda t: triage.clasificar(t, modelo)          # noqa: E731
    elif variante.startswith("torch:"):
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(hilos)
        t1 = time.perf_counter()
        clave = variante.split(":")[1]
        m = SentenceTransformer(str(ruta_modelo(clave, True)), device="cpu")
        m.max_seq_length = MODELOS[clave]["max_len"]
        t2 = time.perf_counter()
        pref = MODELOS[clave]["prefijo"]
        infer = lambda t: m.encode([pref + t], batch_size=1, normalize_embeddings=True)   # noqa: E731
    else:
        import numpy  # noqa: F401
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
        t1 = time.perf_counter()
        e = EmbedORT(variante.split(":")[1], hilos)
        t2 = time.perf_counter()
        infer = lambda t: e([t])                                  # noqa: E731
    infer(textos[0])
    t3 = time.perf_counter()
    lat = []
    for t in textos:
        a = time.perf_counter()
        infer(t)
        lat.append((time.perf_counter() - a) * 1000)
    lat.sort()
    actual, pico = mem_mb()
    print(json.dumps({"variante": variante, "hilos": hilos, "import_s": round(t1 - t0, 3), "carga_s": round(t2 - t1, 3), "primera_s": round(t3 - t2, 3),
                      "arranque_total_s": round(t3 - t0, 3), "lat_mediana_ms": round(lat[len(lat) // 2], 2),
                      "lat_p95_ms": round(lat[int(len(lat) * 0.95) - 1], 2), "n_textos": len(lat), "rss_final_mb": round(actual), "rss_pico_mb": round(pico)}))


# ============================================================================ comprobación previa (API pública, sin descargar)
def comprobar():
    import urllib.request

    def api(repo):
        with urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}?blobs=true", timeout=60) as r:
            return json.load(r)

    def cfg_json(repo, rev, ruta):
        with urllib.request.urlopen(f"https://huggingface.co/{repo}/resolve/{rev}/{ruta}", timeout=60) as r:
            return json.load(r)
    filas = {}
    for clave, repo in [(k, v["hf"]) for k, v in MODELOS.items()] + list(PROPUESTO.items()):
        d = api(repo)
        tam = {s["rfilename"]: s.get("size") or 0 for s in d["siblings"]}
        c = cfg_json(repo, d["sha"], "config.json")
        fila = {"repo": repo, "revision_api": d["sha"], "licencia": (d.get("cardData") or {}).get("license"),
                "parametros": (d.get("safetensors") or {}).get("total"), "pesos_fp32_MB": round(tam.get("model.safetensors", 0) / 1e6, 1),
                "onnx_int8_MB": {k: round(v / 1e6, 1) for k, v in tam.items() if "qint8" in k and k.endswith(".onnx")},
                "onnx_fp32_MB": round(tam.get("onnx/model.onnx", 0) / 1e6, 1), "dim_embedding": c.get("hidden_size") or c.get("hidden_dim"),
                "capas": c.get("num_hidden_layers"), "vocabulario": c.get("vocab_size"),
                "evaluado_aqui": clave in MODELOS, "fecha_comprobacion": time.strftime("%Y-%m-%d")}
        if clave in MODELOS:
            fila["prefijo"], fila["max_seq_usado"] = MODELOS[clave]["prefijo"], MODELOS[clave]["max_len"]
            fila["dependencias_inferencia"] = {"torch+sentence-transformers (fp32)": "torch, transformers, sentence-transformers, numpy",
                                               "onnx int8": "onnxruntime, tokenizers, numpy"}
        filas[clave] = fila
        print(clave, fila["licencia"], fila["parametros"], fila["pesos_fp32_MB"], "MB")
    guardar("comprobacion_previa", filas)


# ============================================================================ experimento
def cargar_entrenar():
    sys.path.insert(0, str(TRIAGE))
    import entrenar
    return entrenar


def datos(E):
    ent = E.leer(TRIAGE / "datos" / "entrenamiento.csv")
    vistos = {E.triage.normalizar(t) for t, _ in ent}
    val, rep_v = E.sin_repetidos(E.leer(TRIAGE / "datos" / "validacion.csv"), vistos)
    pv, rep_p = E.sin_repetidos(E.leer(TRIAGE / "datos" / "prueba.csv"), vistos)
    info = {"entrenamiento": {"n": len(ent), "sha256": sha256_archivo(TRIAGE / "datos" / "entrenamiento.csv")},
            "validacion_ya_vista": {"n": len(val), "repetidos_quitados": rep_v, "sha256": sha256_archivo(TRIAGE / "datos" / "validacion.csv")},
            "prueba_antigua_ya_vista": {"n": len(pv), "repetidos_quitados": rep_p, "sha256": sha256_archivo(TRIAGE / "datos" / "prueba.csv")}}
    return ent, val, pv, info


def embeddings(clave, variante, conjuntos):
    """{nombre: matriz} con caché en HF_HOME/emb (fuera del repo); el cálculo corre en un subproceso para liberar memoria."""
    import numpy as np
    cfg = MODELOS[clave]
    huella = sha256_bytes(json.dumps([clave, cfg["rev"], variante, cfg["prefijo"], cfg["max_len"], conjuntos], sort_keys=True, ensure_ascii=False).encode())[:20]
    base = pathlib.Path(os.environ.get("HF_HOME", pathlib.Path.home() / ".cache" / "huggingface")) / "emb"
    base.mkdir(parents=True, exist_ok=True)
    npz = base / f"{clave}_{variante}_{huella}.npz"
    if not npz.exists():
        entrada = base / f"entrada_{huella}.json"
        entrada.write_text(json.dumps(conjuntos, ensure_ascii=False), encoding="utf-8")
        print(f"  embeddings {clave}/{variante} ({sum(map(len, conjuntos.values()))} textos)…", flush=True)
        subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), "_embed", clave, variante, str(entrada), str(npz)], check=True)
        entrada.unlink()
    z = np.load(npz)
    return {k: z[k] for k in z.files}, leer_json(str(npz) + ".json"), sha256_archivo(npz)


def en_orden(p, clases_modelo, CLASES):
    import numpy as np
    s = np.zeros((p.shape[0], len(CLASES)))
    for j, c in enumerate(clases_modelo):
        s[:, CLASES.index(c)] = p[:, j]
    return s


def elegir_umbral(E, y, oof):
    """Misma regla que entrenar.py: menor umbral >= 0,5 con precisión de servicio >= 98 % y >= 50 reportes (si no, 0,80)."""
    import numpy as np
    pred = [E.CLASES[i] for i in oof.argmax(1)]
    conf = oof.max(1)
    for u in [round(float(x), 2) for x in np.arange(E.PISO_UMBRAL, 0.96, 0.05)]:
        r = E.conteo_servicio(y, pred, conf, u)
        if r["suman"] >= 50 and (r["precision_servicio"] or 0) >= 0.98:
            return u, r
    return 0.80, E.conteo_servicio(y, pred, conf, 0.80)


def ajustar(E, clave, X_ent, y, emb=None):
    """CV (5 pliegues estratificados, solo entrenamiento) -> C -> umbral -> modelo final. Devuelve (objeto_para_predecir, ficha)."""
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import f1_score
    from sklearn.model_selection import StratifiedKFold
    cv = StratifiedKFold(5, shuffle=True, random_state=E.SEMILLA)
    grid = E.GRID_C if clave == "base" else GRID_C_EMB
    f1s, oofs = {}, {}
    for c in grid:
        oof = np.zeros((len(X_ent), len(E.CLASES)))
        for tr, va in cv.split(X_ent, y):
            if clave == "base":
                vocab, idf, m = E.ajustar_lr([X_ent[i] for i in tr], [y[i] for i in tr], c)
                oof[va] = E.probs_lr(vocab, idf, m, [X_ent[i] for i in va])
            else:
                m = LogisticRegression(C=c, max_iter=5000, random_state=E.SEMILLA).fit(emb[tr], [y[i] for i in tr])
                oof[va] = en_orden(m.predict_proba(emb[va]), m.classes_, E.CLASES)
        f1s[c] = round(f1_score(y, [E.CLASES[i] for i in oof.argmax(1)], labels=E.CLASES, average="macro"), 4)
        oofs[c] = oof
        print(f"    {clave:8s} C={c:<6} F1 macro CV = {f1s[c]}", flush=True)
    mejor = max(grid, key=lambda c: f1s[c])
    umbral, st = elegir_umbral(E, y, oofs[mejor])
    if clave == "base":
        vocab, idf, m = E.ajustar_lr(X_ent, y, mejor)
        objeto = ("base", vocab, idf, m)
    else:
        m = LogisticRegression(C=mejor, max_iter=5000, random_state=E.SEMILLA).fit(emb, y)
        objeto = ("emb", m)
    ficha = {"C": mejor, "f1_macro_cv_por_C": {str(k): v for k, v in f1s.items()}, "umbral": umbral, "conteo_cv_con_umbral": st,
             "huella_coeficientes": sha256_bytes(np.ascontiguousarray(m.coef_).tobytes())[:24], "n_iter": int(np.max(m.n_iter_))}
    return objeto, ficha


def predecir(E, objeto, textos=None, emb=None):
    if objeto[0] == "base":
        p = E.probs_lr(objeto[1], objeto[2], objeto[3], textos)
    else:
        p = en_orden(objeto[1].predict_proba(emb), objeto[1].classes_, E.CLASES)
    return [E.CLASES[i] for i in p.argmax(1)], p.max(1), p


def versiones():
    import numpy as np
    import sklearn
    v = {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__, "so": platform.platform(), "cpu": platform.processor()}
    for pk in ("torch", "sentence_transformers", "onnxruntime", "tokenizers", "huggingface_hub"):
        try:
            v[pk] = __import__(pk).__version__
        except Exception:
            v[pk] = None
    return v


def variantes_activas():
    return ["int8", "fp32"] if "--fp32" in sys.argv else ["int8"]


def preparar(E):
    """Datos + embeddings de entrenamiento/ya vistos + ajuste (CV -> C -> umbral -> modelo) de cada candidato. Sin tocar la prueba nueva."""
    ent, val, pv, info = datos(E)
    X, y = [t for t, _ in ent], [e for _, e in ent]
    conj = {"ent": X, "val": [t for t, _ in val], "pv": [t for t, _ in pv]}
    ajustes, fichas, emb, meta = {}, {}, {}, {}
    print("  línea base TF-IDF + LR (código de producción)…", flush=True)
    ajustes["base"], fichas["base"] = ajustar(E, "base", X, y)
    for clave in MODELOS:
        for var in variantes_activas():
            k = f"{clave}_{var}"
            emb[k], meta[k], h = embeddings(clave, var, conj)
            ajustes[k], fichas[k] = ajustar(E, clave, X, y, emb[k]["ent"])
            fichas[k]["embeddings_npz_sha256"] = h[:24]
    return ent, val, pv, info, conj, ajustes, fichas, emb, meta


def congelar():
    from sklearn.metrics import accuracy_score, f1_score
    E = cargar_entrenar()
    ent, val, pv, info, conj, ajustes, fichas, emb, meta = preparar(E)
    print(f"entrenamiento {len(ent)} · validación(ya vista) {len(val)} · prueba antigua(ya vista) {len(pv)}")
    ref = {}
    for nombre, cc, etiquetas in (("validacion_ya_vista", "val", [e for _, e in val]), ("prueba_antigua_ya_vista", "pv", [e for _, e in pv])):
        ref[nombre] = {}
        for k in ajustes:
            pred, conf, _ = predecir(E, ajustes[k], textos=conj[cc]) if k == "base" else predecir(E, ajustes[k], emb=emb[k][cc])
            ref[nombre][k] = {"exactitud": round(accuracy_score(etiquetas, pred), 4),
                              "f1_macro": round(f1_score(etiquetas, pred, labels=E.CLASES, average="macro", zero_division=0), 4),
                              "conteo": E.conteo_servicio(etiquetas, pred, conf, fichas[k]["umbral"])}
    prod = leer_json(TRIAGE / "resultados.json")
    chequeo = {"C_base_igual_a_produccion": fichas["base"]["C"] == prod["configuracion"]["C_elegido_por_cv"],
               "umbral_base_igual_a_produccion": fichas["base"]["umbral"] == prod["umbral_para_sumar_al_conteo"]["umbral"]}
    mod = {"base": fichas["base"]}
    for k in fichas:
        if k != "base":
            clave = k.rsplit("_", 1)[0]
            mod[k] = {**{kk: vv for kk, vv in MODELOS[clave].items() if kk in ("hf", "rev", "prefijo", "max_len", "licencia")}, "variante": k.rsplit("_", 1)[1],
                      **fichas[k], "tokens": meta[k]}
    congelado = {"creado": time.strftime("%Y-%m-%d %H:%M:%S"), "nota": "Escrito ANTES de abrir la prueba nueva. `medir` aborta si los ajustes recalculados no coinciden.",
                 "semilla": SEMILLA, "datos": info, "versiones": versiones(), "regla_de_decision_fijada": REGLA, "variantes": variantes_activas(),
                 "modelos": mod, "chequeo_linea_base": chequeo, "referencia_ya_vista": ref}
    CONGELADO.write_text(json.dumps(congelado, ensure_ascii=False, indent=1), encoding="utf-8")
    guardar("congelado", congelado)
    print("\nCONGELADO:")
    for k, f in fichas.items():
        print(f"  {k:13s} C={f['C']:<6} umbral={f['umbral']}  CV F1 macro={f['f1_macro_cv_por_C'][str(f['C'])]}  huella={f['huella_coeficientes']}")
    print("  chequeo línea base vs producción:", chequeo)
    for nombre, d in ref.items():
        print(" ", nombre, {k: (v["exactitud"], v["f1_macro"]) for k, v in d.items()})


# ---------------------------------------------------------------- métricas de la prueba nueva
def f1_macro_rapido(yr, yp, k):
    import numpy as np
    cm = np.bincount(yr * k + yp, minlength=k * k).reshape(k, k)
    tp = np.diag(cm).astype(float)
    den = 2 * tp + (cm.sum(0) - tp) + (cm.sum(1) - tp)
    return float(np.mean(np.where(den > 0, 2 * tp / np.maximum(den, 1), 0.0)))


def ic(v):
    import numpy as np
    return [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]


def vectores_boot(yi, pi, cuenta, serv, IDX, K):
    import numpy as np
    fp = cuenta & ~serv
    suman, fpb = cuenta[IDX].sum(1), fp[IDX].sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        prec = 1 - fpb / suman
        cob = (cuenta & serv)[IDX].sum(1) / serv[IDX].sum(1)
    return {"acc": (yi[IDX] == pi[IDX]).mean(1), "f1": np.array([f1_macro_rapido(yi[i], pi[i], K) for i in IDX]), "fp": fpb, "prec": prec, "cob": cob}


def evaluar(E, y, perfil, pred, conf, umbral, IDX, base=None):
    """Métricas de UN modelo ya congelado. `base` = dict con lo de la línea base (para la diferencia pareada)."""
    import numpy as np
    from sklearn.metrics import confusion_matrix
    K = len(E.CLASES)
    yi = np.array([E.CLASES.index(c) for c in y])
    pi = np.array([E.CLASES.index(c) for c in pred])
    cuenta = (np.array(pred) != "OTRO") & (np.array(conf) >= umbral)
    serv = np.array(y) != "OTRO"
    fp = cuenta & ~serv
    v = vectores_boot(yi, pi, cuenta, serv, IDX, K)
    r = E.metricas(y, pred)
    r.update({"exactitud_ic95": ic(v["acc"]), "f1_macro_ic95": ic(v["f1"]),
              "matriz_confusion": {"clases": E.CLASES, "filas_real_columnas_predicha": confusion_matrix(y, pred, labels=E.CLASES).tolist()},
              "binaria_conteo": {**E.conteo_servicio(y, pred, conf, umbral), "falsos_positivos": int(fp.sum()), "n_otro": int((~serv).sum()),
                                 "tasa_fp_sobre_otro": round(float(fp.sum() / max(1, (~serv).sum())), 4),
                                 "servicio_que_no_suma": int((serv & ~cuenta).sum()),
                                 "fp_ic95": ic(v["fp"]), "precision_servicio_ic95": ic(v["prec"][np.isfinite(v["prec"])]), "cobertura_ic95": ic(v["cob"])}})
    pp = {}
    for p in PERFILES:
        m = np.array([x == p for x in perfil])
        pp[p] = {"n": int(m.sum()), "errores": int((m & (yi != pi)).sum()), "exactitud": round(float((yi[m] == pi[m]).mean()), 4),
                 "n_otro": int((m & ~serv).sum()), "falsos_positivos": int((fp & m).sum()), "suman": int((cuenta & m).sum()),
                 "servicio_que_no_suma": int((m & serv & ~cuenta).sum()),
                 "errores_por_clase_real": {c: int((m & (yi != pi) & (yi == E.CLASES.index(c))).sum()) for c in E.CLASES if (m & (yi == E.CLASES.index(c))).any()}}
    r["por_perfil"] = pp
    if base is not None:
        ok_c, ok_b = pi == yi, base["pi"] == yi
        r["pareada_vs_base"] = {
            "dif_f1_macro": round(f1_macro_rapido(yi, pi, K) - f1_macro_rapido(yi, base["pi"], K), 4), "dif_f1_macro_ic95": ic(v["f1"] - base["v"]["f1"]),
            "dif_exactitud": round(float(ok_c.mean() - ok_b.mean()), 4), "dif_exactitud_ic95": ic(v["acc"] - base["v"]["acc"]),
            "dif_falsos_positivos": int(fp.sum() - (base["cuenta"] & ~serv).sum()), "dif_fp_ic95": ic(v["fp"] - base["v"]["fp"]),
            "acierta_solo_candidato": int((ok_c & ~ok_b).sum()), "acierta_solo_base": int((~ok_c & ok_b).sum()),
            "por_perfil_[solo_candidato, solo_base]": {p: [int((ok_c & ~ok_b & np.array([x == p for x in perfil])).sum()),
                                                           int((~ok_c & ok_b & np.array([x == p for x in perfil])).sum())] for p in PERFILES}}
    return r


def medir(ruta_prueba):
    import numpy as np
    E = cargar_entrenar()
    if not CONGELADO.exists():
        sys.exit("ERROR: falta congelado.json. Ejecuta primero `congelar` y documenta lo congelado ANTES de medir.")
    cong = json.loads(CONGELADO.read_text(encoding="utf-8"))
    previo = leer_json(RESULTADOS).get("prueba_nueva")
    if previo and previo.get("congelado_creado") != cong["creado"]:
        sys.exit("ERROR: la prueba nueva ya se midió con OTRA congelación. Medirla de nuevo la convierte en validación.")
    if cong["variantes"] != variantes_activas():
        sys.exit(f"ERROR: lo congelado usa las variantes {cong['variantes']}; pasa --fp32 si corresponde.")
    ruta_prueba = pathlib.Path(ruta_prueba or PRUEBA_NUEVA_DEFECTO)
    if not ruta_prueba.exists() and DATOS_PN.exists():
        ruta_prueba = DATOS_PN
    # --- recalcula lo congelado y verifica la huella (todavía sin tocar la prueba nueva)
    ent, val, pv, info, conj, ajustes, fichas, emb, meta = preparar(E)
    for k, f in fichas.items():
        c = cong["modelos"][k]
        assert (f["huella_coeficientes"], f["umbral"], f["C"]) == (c["huella_coeficientes"], c["umbral"], c["C"]), f"{k} no coincide con lo congelado"
    print("Congelado verificado. Abriendo la prueba nueva (una sola medición)…", flush=True)
    # --- AQUÍ se lee por primera vez la prueba nueva
    crudo = ruta_prueba.read_bytes()
    normal = crudo.replace(b"\r\n", b"\n")
    filas = [(r["texto"].strip(), r["etiqueta"].strip(), r["perfil"].strip()) for r in csv.DictReader(io.StringIO(normal.decode("utf-8-sig"), newline=""))]
    assert len(filas) == 280, f"se esperaban 280 filas, hay {len(filas)}"
    assert all(e in E.CLASES for _, e, _ in filas) and all(p in PERFILES for _, _, p in filas), "etiqueta o perfil desconocido"
    Xn, yn, pn = [t for t, _, _ in filas], [e for _, e, _ in filas], [p for _, _, p in filas]
    vistos = {E.triage.normalizar(t) for t, _ in ent + val + pv}
    repetidos = sum(E.triage.normalizar(t) in vistos for t in Xn)
    rng = np.random.default_rng(SEMILLA)
    IDX = np.stack([rng.integers(0, len(yn), len(yn)) for _ in range(N_BOOT)])      # las MISMAS remuestras para todos los modelos
    yi = np.array([E.CLASES.index(c) for c in yn])
    pred_b, conf_b, _ = predecir(E, ajustes["base"], textos=Xn)
    ub = cong["modelos"]["base"]["umbral"]
    pi_b = np.array([E.CLASES.index(c) for c in pred_b])
    cuenta_b = (np.array(pred_b) != "OTRO") & (np.array(conf_b) >= ub)
    base = {"pi": pi_b, "cuenta": cuenta_b, "v": vectores_boot(yi, pi_b, cuenta_b, np.array(yn) != "OTRO", IDX, len(E.CLASES))}
    res = {"base": evaluar(E, yn, pn, pred_b, conf_b, ub, IDX)}
    for k in ajustes:
        if k == "base":
            continue
        clave, var = k.rsplit("_", 1)
        e, _, _ = embeddings(clave, var, {"pn": Xn})
        pred, conf, _ = predecir(E, ajustes[k], emb=e["pn"])
        res[k] = evaluar(E, yn, pn, pred, conf, cong["modelos"][k]["umbral"], IDX, base=base)
    DATOS_PN.parent.mkdir(exist_ok=True)
    DATOS_PN.write_bytes(normal)
    salida = {"congelado_creado": cong["creado"], "n": len(yn), "por_clase_n": {c: yn.count(c) for c in E.CLASES}, "por_perfil_n": {p: pn.count(p) for p in PERFILES},
              "sha256_original": sha256_bytes(crudo), "sha256_copia_lf": sha256_bytes(normal), "textos_ya_vistos_en_entrenamiento_validacion_o_prueba_antigua": repetidos,
              "bootstrap": {"n": N_BOOT, "semilla": SEMILLA, "nota": "mismas remuestras para todos los modelos; IC percentil 2,5-97,5"},
              "umbrales": {k: cong["modelos"][k]["umbral"] for k in cong["modelos"]}, "modelos": res}
    guardar("prueba_nueva", salida)
    decidir()
    resumen(res)


def resumen(res):
    print("\n== PRUEBA NUEVA (n=280) ==")
    for k, r in res.items():
        b, d = r["binaria_conteo"], r.get("pareada_vs_base", {})
        print(f"  {k:12s} exactitud {r['exactitud']:.3f} F1 {r['f1_macro']:.3f} IC{r['f1_macro_ic95']} · FP {b['falsos_positivos']}/{b['n_otro']} · "
              f"prec.serv {b['precision_servicio']} cobertura {b['cobertura']}" + (f" · dF1 {d['dif_f1_macro']:+.3f} IC{d['dif_f1_macro_ic95']}" if d else ""))


# ---------------------------------------------------------------- costos y compatibilidad con Lambda
def tam(ruta):
    ruta = pathlib.Path(ruta)
    return sum(f.stat().st_size for f in ruta.rglob("*") if f.is_file()) if ruta.is_dir() else ruta.stat().st_size


def costos():
    import statistics
    mb = lambda b: round(b / 2 ** 20, 1)   # noqa: E731
    out = {"aviso": "PROXY medido en esta máquina (i7-1255U, sin GPU, Windows, otros procesos activos), no en AWS. Hilos de inferencia = %d. "
                    "Arranque = importaciones + carga + primera inferencia; 3 repeticiones en procesos nuevos, se reporta la mediana." % HILOS_LAMBDA,
           "ejecuciones": {}, "disco": {}}
    variantes = ["base"] + ([f"torch:{k}" for k in MODELOS] if "--fp32" in sys.argv else []) + [f"ort:{k}" for k in MODELOS]
    for v in variantes:
        runs = []
        for _ in range(3):
            p = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()), "_costo", v, str(HILOS_LAMBDA), "150"], capture_output=True, text=True)
            if p.returncode:
                runs.append({"error": p.stderr[-400:]})
                break
            runs.append(json.loads(p.stdout.strip().splitlines()[-1]))
            print("  ", runs[-1], flush=True)
        ok = [r for r in runs if "error" not in r]
        if not ok:
            out["ejecuciones"][v] = {"error": runs[-1]["error"]}
            continue
        med = {k: round(statistics.median(r[k] for r in ok), 3) for k in ("import_s", "carga_s", "primera_s", "arranque_total_s", "lat_mediana_ms", "lat_p95_ms", "rss_pico_mb", "rss_final_mb")}
        med["repeticiones"] = len(ok)
        med["arranque_total_s_por_repeticion"] = [r["arranque_total_s"] for r in ok]
        out["ejecuciones"][v] = med
    for k, cfg in MODELOS.items():
        base = ruta_modelo(k)
        tok = tam(base / "tokenizer.json")
        out["disco"][k] = {"pesos_fp32_safetensors_MB": mb(tam(base / "model.safetensors")) if (base / "model.safetensors").exists() else None, "onnx_int8_MB": mb(tam(base / cfg["int8"])), "tokenizer_json_MB": mb(tok)}
    out["disco"]["base"] = {"triage_modelo.json_KB": round(tam(RAIZ / "services/base/layer/python/telecorp/ml/triage_modelo.json") / 1024), "triage.py_KB": round(tam(RAIZ / "services/base/layer/python/telecorp/ml/triage.py") / 1024, 1)}
    sp = pathlib.Path(sys.executable).parents[1] / "Lib" / "site-packages"
    out["dependencias_instaladas_windows_MB"] = {p: mb(tam(sp / p)) for p in ("torch", "onnxruntime", "numpy", "tokenizers", "transformers", "sentence_transformers", "scipy", "sklearn") if (sp / p).exists()}
    guardar("costos", out)
    print(json.dumps(out["ejecuciones"], indent=1))
    print(json.dumps(viabilidad_lambda(out), indent=1))


def ruedas_linux():
    """Tamaño REAL descomprimido de las ruedas de Linux x86_64 / CPython 3.12 (el runtime de nuestras Lambdas), sin instalarlas."""
    import importlib.metadata as md
    import tempfile
    import zipfile
    d = pathlib.Path(tempfile.mkdtemp(prefix="ruedas_linux_"))
    for pkg in ("onnxruntime", "numpy", "tokenizers"):
        subprocess.run([sys.executable, "-m", "pip", "download", f"{pkg}=={md.version(pkg)}", "--no-deps", "--only-binary=:all:", "--python-version", "3.12",
                        "--implementation", "cp", "--abi", "cp312", "--platform", "manylinux2014_x86_64", "--platform", "manylinux_2_17_x86_64",
                        "--platform", "manylinux_2_28_x86_64", "-d", str(d), "-q"], check=True)
    salida = {}
    for w in sorted(d.glob("*.whl")):
        with zipfile.ZipFile(w) as z:
            salida[w.name] = {"zip_MB": round(w.stat().st_size / 2 ** 20, 1), "descomprimido_MB": round(sum(i.file_size for i in z.infolist()) / 2 ** 20, 1)}
    return salida


def viabilidad_lambda(out):
    ruedas = ruedas_linux()
    deps = round(sum(v["descomprimido_MB"] for v in ruedas.values()), 1)
    res = {"ruedas_linux_x86_64_cp312": ruedas, "dependencias_onnx_descomprimidas_MB": deps,
           "limites": {"capa_descomprimida_MB": 250, "memoria_MB": 1024, "arranque_s": 5},
           "nota": "Paquete = modelo ONNX int8 + tokenizer.json + ruedas Linux (onnxruntime, numpy, tokenizers; sin sympy/coloredlogs/protobuf: ver README) + 0,5 MB de código."}
    for k in MODELOS:
        e, d = out["ejecuciones"].get(f"ort:{k}", {}), out["disco"][k]
        paquete = round(d["onnx_int8_MB"] + d["tokenizer_json_MB"] + deps + 0.5, 1)
        cumple = bool(paquete <= 250 and e.get("rss_pico_mb", 1e9) <= 1024 and e.get("arranque_total_s", 1e9) <= 5)
        res[k] = {"forma_viable": "ONNX int8 + onnxruntime + tokenizers (sin torch)", "paquete_MB": paquete, "rss_pico_MB_proxy": e.get("rss_pico_mb"),
                  "arranque_s_proxy": e.get("arranque_total_s"), "cumple_iii": cumple,
                  "torch_fp32": {"paquete_MB_minimo": round((d["pesos_fp32_safetensors_MB"] or 470.6) + out["dependencias_instaladas_windows_MB"].get("torch", 0), 1),
                                 "cumple": False, "razon": "solo los pesos fp32 + la carpeta de torch instalada superan 250 MB descomprimidos"}}
    guardar("lambda", res)
    return res


# ---------------------------------------------------------------- decisión según la regla fijada
def decidir():
    r = leer_json(RESULTADOS)
    pn, lam, comp = r.get("prueba_nueva"), r.get("lambda"), r.get("comprobacion_previa", {})
    if not pn:
        return
    b = pn["modelos"]["base"]["binaria_conteo"]
    dec = {}
    for k in pn["modelos"]:
        if k == "base":
            continue
        clave, var = k.rsplit("_", 1)
        c = pn["modelos"][k]
        p, bn = c["pareada_vs_base"], c["binaria_conteo"]
        i = p["dif_f1_macro"] >= 0.03 and p["dif_f1_macro_ic95"][0] > 0
        ii = bn["falsos_positivos"] <= b["falsos_positivos"] and (bn["precision_servicio"] or 0) >= (b["precision_servicio"] or 0)
        iii = (lam or {}).get(clave, {}).get("cumple_iii") if var == "int8" else False      # fp32 = torch: no cabe en una capa
        iv = (comp.get(clave, {}).get("licencia") or "") in ("apache-2.0", "mit")
        dec[k] = {"i_f1": bool(i), "ii_conteo_binario": bool(ii), "iii_lambda": iii, "iv_licencia": bool(iv), "reemplazar": bool(i and ii and iii and iv),
                  "detalle": {"dif_f1_macro": p["dif_f1_macro"], "ic95": p["dif_f1_macro_ic95"], "fp_candidato": bn["falsos_positivos"], "fp_base": b["falsos_positivos"],
                              "precision_servicio_candidato": bn["precision_servicio"], "precision_servicio_base": b["precision_servicio"]}}
    dec["veredicto"] = "REEMPLAZAR" if any(v.get("reemplazar") for v in dec.values() if isinstance(v, dict)) else "CONSERVAR el modelo actual"
    guardar("decision", dec)
    print("\nDECISIÓN:", json.dumps(dec, ensure_ascii=False, indent=1))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_embed":
        return trabajador_embed(*sys.argv[2:6])
    if len(sys.argv) > 1 and sys.argv[1] == "_costo":
        return trabajador_costo(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("orden", choices=["comprobar", "congelar", "medir", "costos", "decidir", "todo"])
    ap.add_argument("--prueba-nueva", default=None)
    ap.add_argument("--fp32", action="store_true", help="incluye también los embeddings fp32 con torch (requiere bajar model.safetensors)")
    a = ap.parse_args()
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    if a.orden in ("comprobar", "todo"):
        comprobar()
    if a.orden in ("congelar", "todo"):
        congelar()
    if a.orden in ("costos", "todo"):
        costos()
    if a.orden in ("medir", "todo"):
        medir(a.prueba_nueva)
    if a.orden == "decidir":
        decidir()


if __name__ == "__main__":
    main()
