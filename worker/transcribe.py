"""Transcribe a segmentos + palabras con timestamps.

Devuelve (segments, words):
  segments = [{"start": float, "end": float, "text": str}]
  words    = [{"w": str, "start": float, "end": float}]
"""
import subprocess
import time
from pathlib import Path

import config


_groq_off_until = 0.0  # tras una falla de Groq, se usa Whisper local un rato sin volver a insistir


class _UseLocal(Exception):
    """Groq no puede transcribir ahora (sin cupo, llave mala, caído): se sigue con Whisper local."""


def _run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError(f"ffmpeg falló: {' | '.join(tail)[:300]}")


def transcribe(video: Path, workdir: Path):
    global _groq_off_until
    if config.GROQ_API_KEY and time.time() >= _groq_off_until:
        try:
            return _groq(video, workdir)
        except _UseLocal as e:
            _groq_off_until = time.time() + 600
            print(f"  Transcripción: Groq no disponible ({e}). Sigo con Whisper local (más lento) por 10 min.", flush=True)
    return _local(video, workdir)


def _local(video: Path, workdir: Path):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("Groq no pudo transcribir y falta faster-whisper para el plan B (pip install faster-whisper)")

    wav = workdir / "audio.wav"
    _run(["ffmpeg", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)])
    model = WhisperModel(config.WHISPER_MODEL, compute_type="int8")
    seg_iter, _ = model.transcribe(
        str(wav), language=config.LANGUAGE or None, word_timestamps=True, vad_filter=True
    )
    segments, words = [], []
    for s in seg_iter:
        segments.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        for w in s.words or []:
            words.append({"w": w.word.strip(), "start": w.start, "end": w.end})
    return segments, words


def _groq(video: Path, workdir: Path, chunk_sec: int = 600):
    """Whisper en la nube de Groq. Parte el audio en trozos de 10 min (límite de tamaño por archivo)."""
    import requests

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    total = float(probe.stdout.strip())
    segments, words = [], []
    t = 0.0
    i = 0
    while t < total:
        mp3 = workdir / f"chunk{i}.mp3"
        _run(["ffmpeg", "-y", "-ss", str(t), "-t", str(chunk_sec), "-i", str(video),
              "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(mp3)])
        r = _post_chunk(mp3)
        j = r.json()
        for s in j.get("segments", []):
            segments.append({"start": s["start"] + t, "end": s["end"] + t, "text": s["text"].strip()})
        for w in j.get("words", []):
            words.append({"w": w["word"].strip(), "start": w["start"] + t, "end": w["end"] + t})
        mp3.unlink(missing_ok=True)
        t += chunk_sec
        i += 1
    return segments, words


def _post_chunk(mp3: Path, tries: int = 3):
    """Sube un trozo a Groq. Espera si es un límite corto; si es de largo plazo, cae a Whisper local."""
    import requests

    for attempt in range(tries):
        try:
            with open(mp3, "rb") as f:
                r = requests.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                    files={"file": (mp3.name, f, "audio/mpeg")},
                    data=[
                        ("model", "whisper-large-v3-turbo"),
                        ("response_format", "verbose_json"),
                        ("timestamp_granularities[]", "word"),
                        ("timestamp_granularities[]", "segment"),
                        ("language", config.LANGUAGE),
                    ],
                    timeout=600,
                )
        except requests.RequestException as e:
            raise _UseLocal(f"sin conexión: {type(e).__name__}")
        if r.ok:
            return r
        if r.status_code in (401, 403):
            raise _UseLocal(f"llave rechazada ({r.status_code})")
        if r.status_code in (402, 429):
            try:
                wait = float(r.headers.get("retry-after", ""))
            except ValueError:
                wait = None
            if wait is not None and wait <= 90 and attempt < tries - 1:
                print(f"  Transcripción: límite de Groq, espero {int(wait) + 1} s…", flush=True)
                time.sleep(wait + 1)
                continue
            raise _UseLocal("sin cupo de transcripción")
        if r.status_code >= 500:
            raise _UseLocal(f"Groq caído ({r.status_code})")
        raise RuntimeError(f"Groq transcripción {r.status_code}: {r.text[:200]}")
    raise _UseLocal("sin cupo de transcripción")
