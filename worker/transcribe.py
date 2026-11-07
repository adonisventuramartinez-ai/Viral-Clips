"""Transcribe a segmentos + palabras con timestamps.

Devuelve (segments, words):
  segments = [{"start": float, "end": float, "text": str}]
  words    = [{"w": str, "start": float, "end": float}]
"""
import subprocess
from pathlib import Path

import config


def _run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError(f"ffmpeg falló: {' | '.join(tail)[:300]}")


def transcribe(video: Path, workdir: Path):
    if config.GROQ_API_KEY:
        return _groq(video, workdir)
    return _local(video, workdir)


def _local(video: Path, workdir: Path):
    from faster_whisper import WhisperModel

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
        if not r.ok:
            raise RuntimeError(f"Groq transcripción {r.status_code}: {r.text[:200]}")
        j = r.json()
        for s in j.get("segments", []):
            segments.append({"start": s["start"] + t, "end": s["end"] + t, "text": s["text"].strip()})
        for w in j.get("words", []):
            words.append({"w": w["word"].strip(), "start": w["start"] + t, "end": w["end"] + t})
        mp3.unlink(missing_ok=True)
        t += chunk_sec
        i += 1
    return segments, words
