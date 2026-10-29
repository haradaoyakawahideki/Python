"""La figura del informe: cuántas preguntas acierta Claude en cada modo.

    uv run grafico.py                       # lee resultados.csv y guarda grafico.png
    uv run grafico.py resultados_base.csv
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

AQUI = Path(__file__).parent
MODOS = ["memoria", "web", "mcp"]
RESULTADOS = {"acierta": "#2a9d8f", "no sabe": "#b0b0b0", "se equivoca": "#e76f51"}

res = pd.read_csv(sys.argv[1] if len(sys.argv) > 1 else AQUI / "resultados.csv")
tabla = (res.groupby("modo").resultado.value_counts().unstack(fill_value=0)
         .reindex(index=[m for m in MODOS if m in set(res.modo)], columns=list(RESULTADOS), fill_value=0))
segundos = res.groupby("modo").segundos.mean()

fig, ax = plt.subplots(figsize=(7, 3.2))
izquierda = pd.Series(0, index=tabla.index)
for resultado, color in RESULTADOS.items():
    ax.barh(tabla.index, tabla[resultado], left=izquierda, color=color, label=resultado)
    for modo, n in tabla[resultado].items():
        if n:
            ax.text(izquierda[modo] + n / 2, modo, str(n), ha="center", va="center", color="white", weight="bold")
    izquierda += tabla[resultado]
for modo in tabla.index:
    ax.text(izquierda[modo] + 0.2, modo, f"{segundos[modo]:.1f} s por pregunta", va="center", fontsize=9)

ax.set_xlim(0, len(res.id.unique()) + 3)
ax.set_xlabel("Preguntas")
ax.invert_yaxis()
ax.spines[["top", "right"]].set_visible(False)
ax.legend(ncols=3, loc="lower center", bbox_to_anchor=(0.4, 1.0), frameon=False)
ax.set_title("Claude Haiku con y sin el MCP de ENADES e INEI", pad=28, loc="left")
fig.tight_layout()
fig.savefig(AQUI / "grafico.png", dpi=150)
print(tabla.assign(segundos=segundos.round(1)).to_string())
