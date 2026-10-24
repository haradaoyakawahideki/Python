# Del texto a tu voz: Río Tambo en llamas

Reel de ~60 s, narrado con mi voz clonada, sobre el peor octubre de focos de calor en el distrito de
**Río Tambo (Satipo, Junín)**. El texto de entrada es el README de mi análisis de incendios:
[`Ejercicio/README.md`](../Ejercicio/README.md).

▶️ **Reel:** [`salidas/reel.mp4`](salidas/reel.mp4) · **Posts:** [`salidas/posts.md`](salidas/posts.md) ·
**Subtítulos:** [`salidas/reel.srt`](salidas/reel.srt)

## El flujo

| Paso | Qué | Archivo |
|---|---|---|
| 1 | Texto largo | `../Ejercicio/README.md` |
| 2 | Guion en 7 escenas (`frase`, `cifra`, `etiqueta`) | `guion.json` |
| 3 | Revisión humana del guion contra la fuente | `guion.json` |
| 4 | Voz clonada con Qwen3-TTS 0.6B (en CPU), controlada con Whisper | `voz.py` |
| 5 | Video vertical 1080 × 1920, subtítulos palabra a palabra, ~−14 LUFS | `video.py` |

El notebook [`reel_rio_tambo.ipynb`](reel_rio_tambo.ipynb) recorre los cinco pasos.

## Qué corregí del guion

Revisé cada frase contra el README original:

- **Quité «Oe, causa»** al inicio de la primera escena: la jerga no aportaba nada.
- **Comparación con canchas de fútbol** (escena 6): no está en el README. La verifiqué: una cancha FIFA
  mide ~0,71 ha, así que 1 609 ha son ~2 250 canchas; «más que dos mil» es correcto.
- **«Primera quincena»** (escena 5): el README da los 80 mm para el 1–15 de octubre; la frase lo dice así.
- **Lluvia: correlación, no causa.** El README muestra una correlación de −0,82 entre lluvia y focos,
  no una causa; por eso la escena dice «ojo con la lluvia» y no «por la sequía».
- **«El incendio principal», no «en el distrito».** Las 1 609 ha se midieron en un recuadro alrededor
  del incendio; 1 561 ha están dentro de Río Tambo.
- Se mantuvo la advertencia del README: **un foco de calor no siempre es un incendio**.

## Qué corregí de la voz

El guion estaba bien, pero la voz clonada no siempre lo dijo bien. Whisper oyó:

| Escena | El guion decía | La voz dijo |
|---|---|---|
| 1 | desde dos mil doce | desde muy 12 |
| 5 | ciento veintitrés de promedio | 233 de promedio |
| 6 | mil seiscientas nueve hectáreas | 1.109 hectáreas |

Además, algunas escenas seguían con hasta 19 s de ruido tras la última palabra. El control por WER
(≤ 25 %) dejaba pasar estos errores, así que `voz.py` ahora rechaza y vuelve a generar una escena si
**alguna cifra del guion no se oye tal cual** o si no se oye el final de la frase, y corta cada escena
0,3 s después de su última palabra. En la versión final, todas las cifras se oyen bien.

## Mi voz

La grabación original (`Tarea Diplomados.m4a`) no está en el repositorio. El reel lleva el aviso
«Voz generada con IA» durante todo el video.
