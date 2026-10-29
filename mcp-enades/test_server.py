"""El contrato del servidor: si estas pruebas pasan, Claude Code y evaluar.py pueden usarlo.

    uv run pytest -q

Llaman al servidor en memoria, igual que lo haría Claude Code. Las cifras esperadas salen de los informes, no del
servidor: ENADES 2026 (informe del IEP, pp. 10 y 42) e INEI, Pobreza Monetaria 2016-2025 (cuadro 4.1, p. 72).
"""
import asyncio

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from server import mcp


async def _con_cliente(f):
    async with Client(mcp) as c:
        return await f(c)


def llamar(herramienta, **args):
    return asyncio.run(_con_cliente(lambda c: c.call_tool(herramienta, args))).data


def _pct(datos, respuesta):
    return next(d["pct"] for d in datos if d["respuesta"] == respuesta)


def test_buscar_encuentra_la_desigualdad_economica():
    r = llamar("buscar_preguntas", texto="desigual económicamente", limite=5)
    assert "P06" in [x["variable"] for x in r]
    assert {"variable", "pregunta", "opciones"} <= r[0].keys()


def test_cinco_herramientas_como_minimo():
    nombres = {t.name for t in asyncio.run(_con_cliente(lambda c: c.list_tools()))}
    assert {"buscar_preguntas", "distribucion", "resumen", "pobreza"} <= nombres
    assert len(nombres) >= 5, "falta la herramienta propia"


def test_distribucion_ponderada_como_el_informe():
    r = llamar("distribucion", variable="P16")   # informe IEP, p. 42: «muy grave» entre ricos y pobres
    assert _pct(r["datos"], "Muy grave") == pytest.approx(52.0, abs=0.1)
    assert r["n"] == 1510
    assert r["fuente"].startswith("https://estudiosdeopinion.iep.org.pe")
    r = llamar("distribucion", variable="P15", por="region")   # Lima y el resto del país: 43.6 %
    assert _pct(r["datos"], "Muy grave") == pytest.approx(43.6, abs=0.1)
    assert {g["grupo"] for g in r["grupos"]} == {"Costa", "Sierra", "Selva"}


def test_resumen_sin_cuentas_a_mano():
    r = llamar("resumen", variable="P06")   # informe IEP, p. 10: el 72 % dice muy o algo desigual
    assert r["mas_frecuente"]["respuesta"] == "Mucho"
    d = llamar("distribucion", variable="P06")["datos"]
    assert _pct(d, "Mucho") + _pct(d, "Algo") == pytest.approx(72, abs=0.5)
    assert {"n", "pct_no_sabe"} <= r.keys()


def test_pobreza_del_inei():
    r = llamar("pobreza", ambito="Nacional")   # INEI, cuadro 4.1
    assert len(r["datos"]) == 10
    assert r["datos"][0] == {"anio": 2016, "pct": 20.7}
    assert r["datos"][-1] == {"anio": 2025, "pct": 25.7}
    assert llamar("pobreza", ambito="sierra rural", desde=2025)["datos"] == [{"anio": 2025, "pct": 38.8}]
    assert "cuadro 4.1" in r["fuente"]


def test_percepcion_vs_pobreza():
    r = llamar("percepcion_vs_pobreza", variable="P06", respuesta="Mucho", nivel="ur")
    rural, urbano = r["grupos"]   # de mayor a menor pobreza
    assert (rural["grupo"], rural["pobreza_total"], rural["pobreza_extrema"]) == ("Rural", 35.5, 11.4)
    assert urbano["pobreza_total"] == 23.4
    assert rural["n"] + urbano["n"] == 1510
    assert {"percepcion", "pobreza"} <= r["fuentes"].keys()


def test_variable_inexistente_da_un_error_claro():
    with pytest.raises(ToolError, match="XX999"):
        llamar("distribucion", variable="XX999")


def test_un_recurso_y_un_prompt():
    async def contar(c):
        recursos = len(await c.list_resources()) + len(await c.list_resource_templates())
        return recursos, len(await c.list_prompts())
    recursos, prompts = asyncio.run(_con_cliente(contar))
    assert recursos >= 1 and prompts >= 1
