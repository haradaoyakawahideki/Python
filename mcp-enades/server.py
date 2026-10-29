"""Servidor MCP de la ENADES 2026 (IEP / Oxfam) y la pobreza monetaria del INEI.

    uv run pytest                                             # el contrato: las 8 pruebas deben pasar
    uv run server.py                                          # el servidor, por stdio
    claude mcp add --scope project enades -- uv run server.py # conectarlo a Claude Code

Dos fuentes:
- ENADES 2026: encuesta telefónica a 1,510 personas (28 ene - 2 mar 2026). Microdatos en SPSS, con ponderador.
- INEI, Pobreza Monetaria 2016-2025: cuadros 4.1 (pobreza total) y 4.3 (pobreza extrema) del informe técnico,
  copiados a fuentes/pobreza_inei.csv con su número de cuadro y página.

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import unicodedata
from functools import cache
from pathlib import Path

import httpx
import pandas as pd
import pyreadstat
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

AQUI = Path(__file__).parent
BASE = AQUI / "datos" / "enades_2026.sav"
URL_BASE = "https://estudiosdeopinion.iep.org.pe/wp-content/uploads/2026/12/OXFAM_IEP_ENADES_2026.sav"
FUENTE_ENADES = "https://estudiosdeopinion.iep.org.pe/informe/iii-encuesta-nacional-de-percepcion-de-desigualdades-enades-2026/"
POBREZA = AQUI / "fuentes" / "pobreza_inei.csv"
FUENTE_INEI = ("https://cdn.www.gob.pe/uploads/document/file/9911234/"
               "8087825-informe-tecnico-de-pobreza-monetaria-2016-2025.pdf")
PESO = "ponderab"
NO_SABE = "NS/NP"
SIN_RESPUESTA = "Sin respuesta"   # vacío en la base: NS/NP mal guardado o pregunta que no se le hizo
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}
# variables de la ENADES por las que se puede cruzar, y cómo se llaman sus valores en el INEI
GRUPOS = {"sexo", "edadr", "NSE", "macrozona", "region", "ur", "ambito"}
A_INEI = {"region": {"Costa": "Costa", "Sierra": "Sierra", "Selva": "Selva"},
          "ur": {"Urbano": "Urbana", "Rural": "Rural"}}

mcp = FastMCP("enades", instructions=(
    "Percepciones de desigualdad en el Perú (ENADES 2026, IEP/Oxfam) y pobreza monetaria oficial (INEI 2016-2025). "
    "Busca la variable con buscar_preguntas; usa distribucion o resumen para porcentajes ponderados, pobreza para "
    "las tasas del INEI y percepcion_vs_pobreza para compararlas. No calcules a mano: cita la variable, el cuadro "
    "o la fuente de cada cifra."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode()


@cache
def enades():
    """Los microdatos (345 KB). Se bajan una vez y quedan en datos/. Devuelve (datos, metadatos)."""
    if not BASE.exists():
        BASE.parent.mkdir(exist_ok=True)
        r = httpx.get(URL_BASE, timeout=120, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        BASE.write_bytes(r.content)
    return pyreadstat.read_sav(BASE, apply_value_formats=True)


@cache
def pobreza_inei():
    return pd.read_csv(POBREZA)


def _ficha(variable):
    df, meta = enades()
    if variable not in df.columns or variable == PESO:
        raise ToolError(f"No existe la variable {variable!r}. Búsquenla con buscar_preguntas.")
    opciones = meta.variable_value_labels.get(variable)
    return {"variable": variable, "pregunta": meta.column_names_to_labels.get(variable) or "",
            "tipo": "categorica" if opciones else "numerica",
            "opciones": list(opciones.values()) if opciones else None}


def _pct(df, variable):
    """Porcentaje ponderado de cada respuesta sobre todos los entrevistados, como el informe del IEP."""
    respuestas = df[variable].astype(object).fillna(SIN_RESPUESTA)
    p = df.groupby(respuestas)[PESO].sum() / df[PESO].sum() * 100
    return [{"respuesta": str(k), "pct": round(v, 1)} for k, v in p.sort_values(ascending=False).items()]


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_preguntas(texto: str, limite: int = 10) -> list[dict]:
    """Busca preguntas de la ENADES 2026 por palabras: todas deben aparecer en el código o en el texto.

    Ejemplos: "desigual económicamente", "grave ricos pobres", "lima resto del país", "clase", "impuestos",
    "situación económica hijos". Devuelve la variable (p. ej. "P06"), el texto de la pregunta y sus opciones.
    Si no hay resultados, prueben con menos palabras.
    """
    df, meta = enades()
    palabras = _sin_tildes(texto).split()
    hallados = [c for c in df.columns if c != PESO and
                all(p in _sin_tildes(f"{c} {meta.column_names_to_labels.get(c) or ''}") for p in palabras)]
    return [_ficha(c) for c in hallados[:limite]]


@mcp.tool(annotations=SOLO_LECTURA)
def distribucion(variable: str, por: str | None = None) -> dict:
    """Porcentaje ponderado de cada respuesta a una pregunta de la ENADES 2026, sobre todos los entrevistados.

    variable: código de buscar_preguntas, p. ej. "P06" (¿qué tan desigual es el Perú económicamente?).
    por: cruzar por grupo con "sexo", "edadr" (edad), "NSE", "macrozona", "region" (Costa, Sierra, Selva),
    "ur" (Urbano, Rural) o "ambito". "NS/NP" cuenta como una respuesta más, igual que en el informe del IEP.
    "Sin respuesta" son vacíos en la base: un NS/NP que no se guardó o una pregunta que no se le hizo a todos.
    """
    ficha = _ficha(variable)
    if ficha["tipo"] != "categorica":
        raise ToolError(f"{variable!r} es numérica: usen resumen.")
    df, _ = enades()
    r = {**ficha, "n": len(df), "datos": _pct(df, variable), "fuente": FUENTE_ENADES}
    if por:
        if por not in GRUPOS:
            raise ToolError(f"No se puede cruzar por {por!r}. Usen uno de: {', '.join(sorted(GRUPOS))}.")
        r["por"] = por
        r["grupos"] = [{"grupo": str(g), "n": len(sub), "datos": _pct(sub, variable)}
                       for g, sub in df.groupby(por, observed=True)]
    return r


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(variable: str) -> dict:
    """Resumen ponderado de una pregunta de la ENADES 2026, para no hacer cuentas a mano.

    Categóricas: la respuesta más frecuente, su porcentaje y el porcentaje de NS/NP.
    Numéricas (en esta base, solo "edad"): promedio, mediana, mínimo y máximo. Siempre con n, el número de personas que respondió.
    """
    ficha = _ficha(variable)
    df, _ = enades()
    sub = df[df[variable].notna()]
    r = {"variable": variable, "pregunta": ficha["pregunta"], "tipo": ficha["tipo"], "n": len(sub),
         "fuente": FUENTE_ENADES}
    if ficha["tipo"] == "categorica":
        datos = _pct(df, variable)
        r["mas_frecuente"] = datos[0]
        r["pct_no_sabe"] = next((d["pct"] for d in datos if d["respuesta"] == NO_SABE), 0.0)
        r["pct_sin_respuesta"] = next((d["pct"] for d in datos if d["respuesta"] == SIN_RESPUESTA), 0.0)
    else:
        orden = sub.sort_values(variable)
        acumulado = orden[PESO].cumsum() / orden[PESO].sum()
        r |= {"promedio": round((sub[variable] * sub[PESO]).sum() / sub[PESO].sum(), 1),
              "mediana": float(orden.loc[acumulado >= 0.5, variable].iloc[0]),
              "minimo": float(sub[variable].min()), "maximo": float(sub[variable].max())}
    return r


@mcp.tool(annotations=SOLO_LECTURA)
def pobreza(ambito: str = "Nacional", tipo: str = "total", desde: int = 2016, hasta: int = 2025) -> dict:
    """Incidencia de la pobreza monetaria según el INEI (% de la población), un dato por año entre 2016 y 2025.

    ambito: "Nacional", "Urbana", "Rural", "Costa", "Sierra", "Selva" y, solo para tipo "total", los dominios
    "Costa urbana", "Costa rural", "Sierra urbana", "Sierra rural", "Selva urbana", "Selva rural" y
    "Lima Metropolitana y Callao". tipo: "total" o "extrema".
    """
    df = pobreza_inei()
    sel = df[(df.ambito.map(_sin_tildes) == _sin_tildes(ambito)) & (df.tipo == tipo)]
    if sel.empty:
        validos = sorted(df[df.tipo == tipo].ambito.unique()) or ["total", "extrema"]
        raise ToolError(f"No hay pobreza {tipo!r} para {ambito!r}. Opciones: {', '.join(validos)}.")
    sel = sel[sel.anio.between(desde, hasta)]
    return {"ambito": sel.ambito.iloc[0] if len(sel) else ambito, "tipo": tipo,
            "datos": [{"anio": int(f.anio), "pct": float(f.pct)} for f in sel.itertuples()],
            "fuente": f"{FUENTE_INEI} (cuadro {sel.cuadro.iloc[0]}, p. {sel.pagina.iloc[0]})" if len(sel) else FUENTE_INEI}


@mcp.tool(annotations=SOLO_LECTURA)
def percepcion_vs_pobreza(variable: str, respuesta: str, nivel: str = "region") -> dict:
    """Compara, grupo por grupo, cuánta gente da una respuesta en la ENADES 2026 con la pobreza del INEI en 2025.

    Úsenla para preguntas como "¿se percibe más desigualdad donde hay más pobreza?". Ejemplo:
    variable="P06", respuesta="Mucho", nivel="region" (Costa, Sierra, Selva) o nivel="ur" (Urbano, Rural).
    Devuelve, por grupo, el % ponderado que dio esa respuesta, su n y la pobreza total y extrema del INEI,
    ordenados de mayor a menor pobreza, con las dos fuentes.
    """
    if nivel not in A_INEI:
        raise ToolError(f"nivel debe ser uno de: {', '.join(A_INEI)}. El INEI no publica los otros grupos.")
    ficha = _ficha(variable)
    if ficha["tipo"] != "categorica" or respuesta not in ficha["opciones"]:
        raise ToolError(f"{respuesta!r} no es una respuesta de {variable!r}. Opciones: {ficha['opciones']}.")
    df, _ = enades()
    inei = pobreza_inei().query("anio == 2025").set_index(["ambito", "tipo"]).pct
    filas = []
    for g, sub in df.groupby(nivel, observed=True):
        pct = next((d["pct"] for d in _pct(sub, variable) if d["respuesta"] == respuesta), 0.0)
        a = A_INEI[nivel][str(g)]
        filas.append({"grupo": str(g), "n": len(sub), "pct_respuesta": pct,
                      "pobreza_total": float(inei[(a, "total")]), "pobreza_extrema": float(inei[(a, "extrema")])})
    return {"variable": variable, "pregunta": ficha["pregunta"], "respuesta": respuesta, "nivel": nivel,
            "grupos": sorted(filas, key=lambda f: -f["pobreza_total"]),
            "fuentes": {"percepcion": FUENTE_ENADES, "pobreza": f"{FUENTE_INEI} (cuadros 4.1 y 4.3, 2025)"}}


@mcp.resource("enades://pregunta/{variable}")
def pregunta(variable: str) -> dict:
    """Texto completo de una pregunta de la ENADES 2026 y sus opciones de respuesta."""
    return _ficha(variable)


@mcp.prompt
def informe(tema: str) -> str:
    """Informe corto sobre un tema de desigualdad, con cifras verificables."""
    return (f"Escribe 5 viñetas sobre «{tema}» en el Perú. Busca las preguntas con buscar_preguntas y saca cada "
            "cifra de distribucion, resumen, pobreza o percepcion_vs_pobreza. En cada viñeta cita la variable de la "
            "ENADES 2026 o el cuadro del INEI, y el n cuando sea un subgrupo. Si un grupo tiene menos de 100 "
            "personas, dilo: su porcentaje es poco preciso.")


if __name__ == "__main__":
    mcp.run()
