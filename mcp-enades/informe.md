# Informe · ¿Le sirve a Claude un MCP de la ENADES 2026 y el INEI?

## 1. Qué construí

Elegí dos fuentes para este proyecto. La primera es la ENADES, producida por el IEP y Oxfam. Esta mide la percepción de desigualdad en el Perú. La segunda es la pobreza monetaria del INEI (2016-2025).

| Herramienta | Para qué sirve |
|---|---|
| `buscar_preguntas` | Encuentra el código de una pregunta de la ENADES (p. ej. P06) a partir de palabras clave, con su texto y opciones. |
| `distribucion` | Da el porcentaje ponderado de cada respuesta a una pregunta, en total o cruzado por sexo, edad, NSE, macrozona, región o ámbito. |
| `resumen` | Resume una pregunta sin hacer cuentas a mano: respuesta más frecuente, su porcentaje, NS/NP y n (o promedio y mediana si es numérica). |
| `pobreza` | Devuelve la pobreza monetaria total o extrema del INEI por año (2016-2025) y por ámbito, región natural o dominio. |
| `percepcion_vs_pobreza` (propia) | Pone lado a lado, por región natural o urbano/rural, el % que da una respuesta en la ENADES y la pobreza del INEI 2025. |

Recurso: `enades://pregunta/{variable}` · Prompt: `/mcp__enades__informe`.

**El recurso con @ en Claude Code:**

![Recurso enades://pregunta/P06 adjuntado con @](capturas/recurso.png)

**El prompt con / en Claude Code:**

![Prompt /mcp__enades__informe desigualdad territorial](capturas/prompt.png)


## 2. Cómo lo medí

- 10 preguntas en `preguntas.csv`: 4 de la ENADES, 4 del INEI y 2 mías sobre P09 (autopercepción de clase).
- La verdad de cada pregunta sale de los informes publicados, no del MCP.
- `evaluar.py` con Claude Haiku, en tres modos: `memoria` (sin herramientas), `web` (WebSearch y WebFetch) y `mcp`.
- `resultados_base.csv`: corrida memoria vs. mcp. `resultados.csv`: experimento extra con los tres modos.

## 3. Resultados

![Aciertos por modo](grafico.png)

| Modo | Acierta | No sabe | Se equivoca | Segundos por pregunta |
|---|---|---|---|---|
| memoria | 0 | 10 | 0 | 4.8 |
| web | 4 | 6 | 0 | 24.4 |
| mcp | 10 | 0 | 0 | 8.2 |

## 4. Qué acertó y qué no, y por qué

**Memoria.** Respondió «no sabe» en las 10 preguntas, posiblemente porque los informes son posteriores a los datos de entrenamiento del modelo. No acierta ninguna, pero tampoco inventa cifras.

**Web.** Acertó 4: las tres cifras nacionales del INEI (pobreza total, extrema y rural 2025) y P06 «muy o algo» (72 % frente a 71.5 %, probablemente el valor redondeado del informe). Respondió «no sabe» en las otras 6: P14, P15, P16, los dos cruces de P09 y la pobreza de la Sierra rural. Esas cifras no aparecen tal cual en la web y salen de los microdatos o de cuadros desagregados. Además, tardó unas tres veces más que el MCP.

**MCP.** Acierta las 10, porque calcula los porcentajes ponderados directamente sobre los microdatos de la ENADES y lee las tasas de los cuadros del INEI, en vez de buscarlos en textos publicados.

## 5. Lo que encontré sobre desigualdad

No se percibe más desigualdad donde hay más pobreza. En la zona rural, donde la pobreza es de 35.5 % frente a 23.4 % en la urbana, solo el 37.7 % dice que el Perú es «muy» desigual, frente a 55.2 % en la urbana (P06). La desigualdad entre ciudades y zonas rurales se ve igual: la califica de «muy grave» el 38.5 % en la zona rural y el 51.4 % en la urbana (P14).

La Selva es el caso que más se aparta. Tiene una pobreza parecida a la de la Sierra (27.3 % y 28.6 %), pero solo el 41.4 % responde «Mucho» en P06, frente a 52.6 % en la Sierra. La diferencia no se debe a NS/NP (4.6 %), sino a «Poco» (32 % frente a 20.1 %).

Con solo 2 o 3 grupos, son comparaciones descriptivas, no correlaciones. Además, los subgrupos más chicos (Centro, n = 147; Selva, n = 202; rural, n = 272) tienen márgenes de error de unos ±6 a 8 puntos.

## 6. Dos cifras comprobadas a mano

| Cifra | Dónde la comprobé | Valor publicado | Valor del MCP |
|---|---|---|---|
| P09 «Baja», Perú rural | [Informe IEP ENADES 2026, p. 118](https://estudiosdeopinion.iep.org.pe/wp-content/uploads/2026/12/Oxfam-IEP.-ENADES-2026.-Informe.pdf) | 37 % | 37.3 % |
| Pobreza monetaria rural 2025 | [INEI, cuadro 4.1, p. 72](https://cdn.www.gob.pe/uploads/document/file/9911234/8087825-informe-tecnico-de-pobreza-monetaria-2016-2025.pdf) | 35 % | 35.5 % |

## 7. Limitaciones

- La ENADES tiene 1,510 entrevistas: los cruces por grupos pequeños (p. ej. rural, n = 272) son menos precisos.
- La comparación con el INEI solo es posible por área y región natural.

## 8. Conclusión

Claude fue útil para contrastar información de INEI y la ENADES. Es interesante ver esta forma en que la IA no alucina datos cuando el MCP puede limitar sus fuentes. 
