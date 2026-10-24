"""Paso 4: narrar guion.json con la voz clonada (Qwen3-TTS) y controlar cada escena con Whisper."""
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import jiwer
import re
import unicodedata
from num2words import num2words
import numpy as np
import soundfile as sf
import torch
from faster_whisper import WhisperModel
from qwen_tts import Qwen3TTSModel

AQUI = Path(__file__).parent
SALIDAS = AQUI / "salidas"
VOZ_ORIGINAL = AQUI / "Tarea Diplomados.m4a"
MODELO_TTS = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
PAUSA_S = 0.35          # silencio entre escenas
MAX_WER = 0.25          # si Whisper entiende mal más del 25 %, se regenera
INTENTOS = 5
COLA_S = 0.3            # se corta 0,3 s después de la última palabra
TOKENS_POR_S = 12       # el códec de Qwen3-TTS va a 12 Hz
CARACTERES_POR_S = 14   # ritmo aproximado de lectura en español


def a_wav(origen, destino, sr=24000):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(origen),
                    "-ac", "1", "-ar", str(sr), str(destino)], check=True)


def a_16k(audio, sr):
    """Whisper recibe arreglos a 16 kHz (evita el decodificador de av)."""
    n = int(len(audio) * 16000 / sr)
    return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)


def normalizar(texto):
    # Whisper escribe "1.609" o "335"; el guion dice "mil seiscientas nueve"
    texto = re.sub(r"(?<=\d)[.,](?=\d{3})", "", texto.replace("%", " por ciento").replace("-", " "))
    texto = re.sub(r"\d+", lambda m: num2words(int(m.group()), lang="es"), texto)
    texto = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    texto = texto.replace("ientas", "ientos")
    palabras = jiwer.RemovePunctuation()(texto).split()
    # Whisper oye "pocos" en esta voz, también en la grabación original
    return ["focos" if p == "pocos" else p for p in palabras]


NUMEROS = {p for n in range(1001) for p in normalizar(num2words(n, lang="es"))} - {"y"}


def cifras(palabras):
    """Tramos de palabras numéricas del guion: «ciento veintitres», «dos mil doce»..."""
    tramos, actual = [], []
    for k, p in enumerate(palabras):
        sigue_numero = k + 1 < len(palabras) and palabras[k + 1] in NUMEROS
        if p in NUMEROS or (p == "y" and actual and sigue_numero):
            actual.append(p)
        elif actual:
            tramos.append(" ".join(actual))
            actual = []
    return tramos + ([" ".join(actual)] if actual else [])


def evaluar(escena, audio, sr, whisper):
    """Devuelve (motivo de rechazo o None, WER, audio recortado tras la última palabra)."""
    guion = normalizar(escena["frase"])
    segs, _ = whisper.transcribe(a_16k(audio, sr), language="es", word_timestamps=True)
    palabras = [w for s in segs for w in s.words]
    # Whisper parte "1.609" en " 1" y ".609": se normaliza el texto acumulado, no palabra por palabra
    fin, corte = None, []
    for k, w in enumerate(palabras):
        corte = normalizar("".join(x.word for x in palabras[: k + 1]))
        if corte[-2:] == guion[-2:]:
            fin = w.end
            break
    if fin is None:
        return "no se oye el final de la frase", 1.0, audio
    recortado = audio[: int((fin + COLA_S) * sr)]
    wer = jiwer.wer(" ".join(guion), " ".join(corte))
    faltan = [c for c in cifras(guion) if f" {c} " not in f" {' '.join(corte)} "]
    if faltan:
        return f"cifras mal dichas: {faltan}", wer, recortado
    if wer > MAX_WER:
        return f"WER {wer:.0%}", wer, recortado
    return None, wer, recortado


def main():
    SALIDAS.mkdir(exist_ok=True)
    (SALIDAS / "escenas").mkdir(exist_ok=True)
    escenas = json.loads((AQUI / "guion.json").read_text())["escenas"]

    ref_wav = SALIDAS / "mi_voz.wav"
    a_wav(VOZ_ORIGINAL, ref_wav)
    whisper = WhisperModel("small", device="cpu", compute_type="int8")
    voz, sr_voz = sf.read(ref_wav, dtype="float32")
    segs, _ = whisper.transcribe(a_16k(voz, sr_voz), language="es")
    # Whisper oyó "pocos de calor": se corrige a lo que se dijo
    ref_text = " ".join(s.text.strip() for s in segs).replace("pocos de calor", "focos de calor")
    print("Transcripción de la voz:", ref_text)

    dispositivo = "cpu"  # en MPS falla el codificador de audio (más de 65 536 canales)
    tts = Qwen3TTSModel.from_pretrained(MODELO_TTS, device_map=dispositivo, dtype=torch.float32)
    prompt = tts.create_voice_clone_prompt(ref_audio=str(ref_wav), ref_text=ref_text)

    pistas, tiempos, t = [], [], 0.0
    for i, escena in enumerate(escenas, 1):
        mejor = None
        hecha = SALIDAS / "escenas" / f"escena_{i}.wav"
        if hecha.exists():  # retomar: se reusan las escenas ya narradas si pasan el control
            audio, sr = sf.read(hecha, dtype="float32")
            motivo, wer, audio = evaluar(escena, audio, sr, whisper)
            print(f"Escena {i}: reusada, WER {wer:.0%}" + (f" -> se rehace ({motivo})" if motivo else ""))
            mejor = (motivo is not None, wer, audio)
        for intento in range(1, INTENTOS + 1):
            if mejor is not None and not mejor[0]:
                break
            # tope de duración: sin él, el modelo a veces no se detiene al terminar la frase
            esperado_s = len(escena["frase"]) / CARACTERES_POR_S
            wavs, sr = tts.generate_voice_clone(text=escena["frase"], language="Spanish",
                                                voice_clone_prompt=prompt,
                                                max_new_tokens=int(esperado_s * 2 * TOKENS_POR_S))
            motivo, wer, audio = evaluar(escena, wavs[0].astype(np.float32), sr, whisper)
            print(f"Escena {i}, intento {intento}: WER {wer:.0%}" + (f" -> rechazada ({motivo})" if motivo else " OK"))
            if mejor is None or (motivo is None, -wer) > (not mejor[0], -mejor[1]):
                mejor = (motivo is not None, wer, audio)
        if mejor[0]:
            print(f"AVISO escena {i}: ningún intento pasó el control; revisar a oído")
        _, wer, audio = mejor
        sf.write(SALIDAS / "escenas" / f"escena_{i}.wav", audio, sr)
        dur = len(audio) / sr
        tiempos.append({"escena": i, "inicio": t, "fin": t + dur, "wer": wer})
        pistas += [audio, np.zeros(int(PAUSA_S * sr), dtype=np.float32)]
        t += dur + PAUSA_S

    sf.write(SALIDAS / "reel.wav", np.concatenate(pistas), sr)
    (SALIDAS / "tiempos.json").write_text(json.dumps(tiempos, indent=2))
    print(f"reel.wav: {t:.1f} s")


if __name__ == "__main__":
    main()
