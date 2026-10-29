# MCP · Percepción de desigualdad (ENADES 2026) y pobreza (INEI)

Servidor MCP con FastMCP que responde con cifras ponderadas de la **ENADES 2026** (IEP / Oxfam, 1,510 entrevistas,
ene–mar 2026) y con la **pobreza monetaria oficial del INEI 2016–2025**, y las compara.

| Herramienta | Qué hace |
|---|---|
| `buscar_preguntas(texto)` | Busca entre las 125 variables de la ENADES por el texto de la pregunta |
| `distribucion(variable, por)` | % ponderado de cada respuesta, opcionalmente por sexo, edad, NSE, macrozona, región o área |
| `resumen(variable)` | Respuesta más frecuente y % de NS/NP (o promedio y mediana si es numérica) |
| `pobreza(ambito, tipo, desde, hasta)` | Serie anual del INEI: pobreza total o extrema por área, región natural o dominio |
| `percepcion_vs_pobreza(variable, respuesta, nivel)` | **Propia.** Por región natural o área, el % que da una respuesta junto a la pobreza del INEI 2025 |

Además, el recurso `enades://pregunta/{variable}` y el prompt `informe(tema)`.

## Fuentes

- ENADES 2026: microdatos `.sav` de la [página del IEP](https://estudiosdeopinion.iep.org.pe/informe/iii-encuesta-nacional-de-percepcion-de-desigualdades-enades-2026/).
  Se bajan solos a `datos/`, que git ignora. Todas las cifras usan el ponderador `ponderab`.
- INEI: cuadros 4.1 y 4.3 del [informe técnico de pobreza 2016–2025](https://www.gob.pe/institucion/inei/informes-publicaciones/8087825-cifras-de-pobreza-2025),
  copiados a `fuentes/pobreza_inei.csv` con su cuadro y página.

## Uso

```bash
uv run pytest -q          # 8 pruebas; las cifras esperadas salen de los informes, no del servidor
uv run evaluar.py         # cada pregunta de preguntas.csv sin MCP y con él
claude                    # desde esta carpeta: .mcp.json conecta enades y fetch
```
