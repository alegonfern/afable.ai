"""
Sandbox de análisis Python del agente ("Científico de Datos").

Ejecuta código pandas/matplotlib escrito por el LLM en un subproceso aislado:
sin variables de entorno del backend (ni secrets ni settings), sin acceso a la
BD — los datos entran como DataFrames pre-consultados por la capa run_sql de
solo lectura — y con timeout duro. Las figuras matplotlib se capturan como PNG
y NUNCA viajan al contexto del modelo: el tool result lleva marcadores
[[FIGURA_n]] que la vista sustituye por la imagen real en la respuesta final.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile

TIMEOUT_SECONDS = 60
MAX_STDOUT = 6000  # chars devueltos al modelo
MAX_FIGURES = 4

# Preámbulo que corre antes del código del modelo dentro del subproceso.
_RUNNER = r"""
import json, sys, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Estilo Afable para las figuras
plt.rcParams.update({
    "figure.figsize": (8, 4.5), "figure.dpi": 110,
    "axes.prop_cycle": matplotlib.cycler(color=[
        "#586AD0", "#2F42A6", "#F59E0B", "#EC4899", "#10B981", "#6366F1"]),
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "grid.linewidth": 0.6,
    "axes.titlesize": 12, "axes.titleweight": "bold",
    "font.size": 9.5,
})

_workdir = sys.argv[1]
with open(os.path.join(_workdir, "datasets.json"), encoding="utf-8") as _f:
    _datasets = json.load(_f)

def _coerce_numeric(df):
    # Los Decimal de SQL llegan serializados como string; sin esto matplotlib
    # trata los montos como categorías y el gráfico queda con el eje mentiroso.
    for _c in df.columns:
        if (df[_c].dtype == object or pd.api.types.is_string_dtype(df[_c])) and df[_c].notna().any():
            _conv = pd.to_numeric(df[_c], errors="coerce")
            if _conv.notna().sum() == df[_c].notna().sum():
                df[_c] = _conv
    return df

dfs = {name: _coerce_numeric(pd.DataFrame(rows)) for name, rows in _datasets.items()}
globals().update(dfs)

with open(os.path.join(_workdir, "code.py"), encoding="utf-8") as _f:
    _code = _f.read()
exec(compile(_code, "analisis.py", "exec"), globals())

for _i, _num in enumerate(plt.get_fignums()):
    if _i >= %(max_figures)d:
        break
    plt.figure(_num).savefig(os.path.join(_workdir, f"fig_{_i + 1}.png"),
                             bbox_inches="tight", facecolor="white")
""" % {"max_figures": MAX_FIGURES}


def run_python(code: str, datasets: dict[str, list[dict]]) -> dict:
    """Ejecuta `code` con `datasets` disponibles como DataFrames.

    Devuelve {'stdout', 'figures': [png_base64, ...], 'error'?}. Las claves de
    `datasets` quedan como variables globales DataFrame (y también en `dfs`).
    """
    with tempfile.TemporaryDirectory(prefix="afable_sandbox_") as workdir:
        with open(os.path.join(workdir, "datasets.json"), "w", encoding="utf-8") as f:
            json.dump(datasets, f, ensure_ascii=False, default=str)
        with open(os.path.join(workdir, "code.py"), "w", encoding="utf-8") as f:
            f.write(code)
        with open(os.path.join(workdir, "runner.py"), "w", encoding="utf-8") as f:
            f.write(_RUNNER)

        env = {
            "HOME": workdir,  # matplotlib necesita un dir de config escribible
            "MPLCONFIGDIR": os.path.join(workdir, ".mpl"),
            "PATH": os.environ.get("PATH", ""),
        }
        try:
            proc = subprocess.run(
                [sys.executable, "-I", os.path.join(workdir, "runner.py"), workdir],
                capture_output=True, text=True, cwd=workdir, env=env,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {"error": f"El análisis superó el límite de {TIMEOUT_SECONDS}s. Simplifica el código."}

        stdout = (proc.stdout or "").strip()
        if len(stdout) > MAX_STDOUT:
            stdout = stdout[:MAX_STDOUT] + "\n… (salida truncada)"

        if proc.returncode != 0:
            stderr_tail = "\n".join((proc.stderr or "").strip().splitlines()[-12:])
            return {"stdout": stdout, "error": f"El código falló:\n{stderr_tail}"}

        figures = []
        for i in range(1, MAX_FIGURES + 1):
            path = os.path.join(workdir, f"fig_{i}.png")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    figures.append(base64.b64encode(f.read()).decode())

        return {"stdout": stdout, "figures": figures}
