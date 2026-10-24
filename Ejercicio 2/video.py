"""Paso 5: reel.wav + guion.json -> reel.mp4 vertical con subtítulos palabra a palabra (Whisper)."""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw, ImageFont

from voz import SALIDAS, a_16k

AQUI = Path(__file__).parent
ANCHO, ALTO, FPS = 1080, 1920, 30
CIERRE_S = 3.0
MARGEN = 90                      # zonas seguras: nada importante en los bordes
FONDO, TEXTO, GRIS, NARANJA = (18, 20, 24), (245, 245, 240), (165, 168, 175), (255, 140, 40)
AUTOR = "Hideki Harada"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_B = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
ARIAL_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"


def fuente(ruta, tam):
    return ImageFont.truetype(ruta, tam)


def envolver(draw, texto, f, ancho):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if draw.textlength(prueba, font=f) <= ancho:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return lineas + [actual]


def tiempos_de_palabras(escena, audio, sr, inicio, whisper):
    """Palabras del guion con sus tiempos; Whisper da los tiempos, el guion da la ortografía."""
    palabras = escena["frase"].split()
    segs, _ = whisper.transcribe(a_16k(audio, sr), language="es", word_timestamps=True)
    oidas = [w for s in segs for w in s.words]
    dur = len(audio) / sr
    if len(oidas) == len(palabras):
        return [(p, inicio + w.start, inicio + w.end) for p, w in zip(palabras, oidas)]
    # si no coinciden, se reparte el tiempo según el largo de cada palabra
    pesos = np.array([len(p) + 1 for p in palabras], dtype=float)
    bordes = np.concatenate([[0], np.cumsum(pesos)]) / pesos.sum() * dur
    return [(p, inicio + a, inicio + b) for p, a, b in zip(palabras, bordes[:-1], bordes[1:])]


def bloques(palabras, n=4):
    return [palabras[i:i + n] for i in range(0, len(palabras), n)]


def lienzo():
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    d.text((MARGEN, 230), "RÍO TAMBO · SATIPO, JUNÍN", font=fuente(ARIAL_B, 38), fill=NARANJA)
    d.text((MARGEN, 285), "Incendios · octubre 2026", font=fuente(ARIAL, 36), fill=GRIS)
    aviso = "Voz generada con IA"
    f = fuente(ARIAL_B, 30)
    w = d.textlength(aviso, font=f)
    d.rounded_rectangle((ANCHO - MARGEN - w - 36, 225, ANCHO - MARGEN, 275), 12, fill=(45, 48, 55))
    d.text((ANCHO - MARGEN - w - 18, 233), aviso, font=f, fill=TEXTO)
    return img, d


def tarjeta(escena):
    img, d = lienzo()
    y = 620
    if escena["cifra"]:
        f = fuente(ARIAL_BLACK, 230)
        while d.textlength(escena["cifra"], font=f) > ANCHO - 2 * MARGEN:
            f = fuente(ARIAL_BLACK, f.size - 10)
        d.text((MARGEN, y), escena["cifra"], font=f, fill=NARANJA)
        y += f.size + 60
    f = fuente(ARIAL_B, 54)
    for linea in envolver(d, escena["etiqueta"], f, ANCHO - 2 * MARGEN):
        d.text((MARGEN, y), linea, font=f, fill=TEXTO)
        y += 70
    return img


def cierre():
    img, d = lienzo()
    y = 700
    for texto, f, color in [
        ("Fuentes", fuente(ARIAL_B, 46), NARANJA),
        ("NASA FIRMS · INPE Queimadas", fuente(ARIAL, 46), TEXTO),
        ("Sentinel-2 · Open-Meteo · INEI", fuente(ARIAL, 46), TEXTO),
        ("", None, None),
        (f"Análisis y voz: {AUTOR}", fuente(ARIAL_B, 46), TEXTO),
        ("Voz clonada con Qwen3-TTS", fuente(ARIAL, 40), GRIS),
    ]:
        if texto:
            d.text((MARGEN, y), texto, font=f, fill=color)
        y += 75
    return img


def subtitulo(img, bloque, t):
    d = ImageDraw.Draw(img)
    f = fuente(ARIAL_B, 62)
    texto = " ".join(p for p, _, _ in bloque)
    lineas = envolver(d, texto, f, ANCHO - 2 * MARGEN)
    y = 1380
    i = 0
    for linea in lineas:
        x = (ANCHO - d.textlength(linea, font=f)) / 2
        for palabra in linea.split():
            p, a, b = bloque[i]
            color = NARANJA if a <= t < b else TEXTO
            d.text((x, y), palabra, font=f, fill=color, stroke_width=3, stroke_fill=FONDO)
            x += d.textlength(palabra + " ", font=f)
            i += 1
        y += 80


def srt(palabras):
    def hms(s):
        ms = int(round(s * 1000))
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    filas = []
    for n, b in enumerate(bloques(palabras, 7), 1):
        filas.append(f"{n}\n{hms(b[0][1])} --> {hms(b[-1][2])}\n{' '.join(p for p, _, _ in b)}\n")
    return "\n".join(filas)


def main():
    guion = json.loads((AQUI / "guion.json").read_text())
    escenas = guion["escenas"]
    tiempos = json.loads((SALIDAS / "tiempos.json").read_text())
    whisper = WhisperModel("small", device="cpu", compute_type="int8")

    palabras, por_escena = [], []
    for escena, tt in zip(escenas, tiempos):
        audio, sr = sf.read(SALIDAS / "escenas" / f"escena_{tt['escena']}.wav", dtype="float32")
        ps = tiempos_de_palabras(escena, audio, sr, tt["inicio"], whisper)
        palabras += ps
        por_escena.append((tarjeta(escena), bloques(ps), tt))
    (SALIDAS / "reel.srt").write_text(srt(palabras))

    voz, sr = sf.read(SALIDAS / "reel.wav", dtype="float32")
    total = len(voz) / sr + CIERRE_S
    final = cierre()
    por_escena[0][0].save(SALIDAS / "portada.png")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    proc = subprocess.Popen([
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{ANCHO}x{ALTO}", "-r", str(FPS), "-i", "-",
        "-i", str(SALIDAS / "reel.wav"),
        "-af", f"volume=20dB,acompressor=threshold=-24dB:ratio=4:attack=5:release=80,loudnorm=I=-14:TP=-1.5:LRA=11,apad=whole_dur={total}", "-ar", "48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart",
        str(SALIDAS / "reel.mp4"),
    ], stdin=subprocess.PIPE)

    for k in range(int(total * FPS)):
        t = k / FPS
        actual = next((e for e in por_escena if t < e[2]["fin"] + 0.35), None)
        if actual is None:
            img = final
        else:
            fondo, bs, _ = actual
            img = fondo.copy()
            bloque = next((b for b in bs if t < b[-1][2]), None)
            if bloque and t >= bs[0][0][1] - 0.1:
                subtitulo(img, bloque, t)
        proc.stdin.write(img.tobytes())
    proc.stdin.close()
    proc.wait()
    print(f"reel.mp4: {total:.1f} s")


if __name__ == "__main__":
    main()
