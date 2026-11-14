"""Transcribe a segmentos + palabras con timestamps.

Devuelve (segments, words):
  segments = [{"start": float, "end": float, "text": str}]
  words    = [{"w": str, "start": float, "end": float}]
"""
import subprocess
import time
from pathlib import Path

import config

import re

_groq_off_until = 0.0  # tras una falla de Groq, se usa Whisper local un rato sin volver a insistir
_key_cool = {}         # llave -> hora hasta la que descansa (sin cupo)
_key_dead = set()      # llaves rechazadas (401/403)
_key_rr = 0            # reparto: cada trozo empieza por una llave distinta
_DAILY = re.compile(r"per day|daily|per_day|perday|per-day|\basd\b", re.I)
_HOURLY = re.compile(r"per hour|per_hour|per-hour|\bash\b", re.I)


class _UseLocal(Exception):
    """Groq no puede transcribir ahora (sin cupo, llave mala, caído): se sigue con Whisper local."""


def _run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError(f"ffmpeg falló: {' | '.join(tail)[:300]}")


class _KeyBad(Exception):
    """Esta llave fue rechazada (401/403): no sirve."""


class _KeyBusy(Exception):
    """Esta llave se quedó sin cupo (429): probar otra."""
    def __init__(self, wait, msg):
        super().__init__(msg)
        self.wait = wait


def _get_groq_keys():
    """Todas las llaves de Groq (3, 20 o las que tengas), limpias y sin repetir."""
    return config.groq_keys()


def transcribe(video: Path, workdir: Path):
    global _groq_off_until
    keys = _get_groq_keys()
    if keys and time.time() >= _groq_off_until:
        try:
            return _groq(video, workdir, keys)
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
        str(wav), language=config.LANGUAGE or None, word_timestamps=True, vad_filter=True,
        initial_prompt=config.whisper_prompt() or None,
    )
    segments, words = [], []
    for s in seg_iter:
        segments.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        for w in s.words or []:
            words.append({"w": w.word.strip(), "start": w.start, "end": w.end})
    return segments, words


def _duration(video: Path):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    return float(probe.stdout.strip())


def _groq(video: Path, workdir: Path, keys: list, chunk_sec: int = None):
    """Whisper en la nube de Groq con todas las llaves disponibles.

    Cada trozo se corta con unos segundos extra a cada lado y luego se recorta en la frontera, así una palabra
    que cae justo entre dos trozos sale completa una sola vez (antes salía cortada o se perdía).
    """
    chunk_sec = chunk_sec or config.TRANSCRIBE_CHUNK
    pad = config.TRANSCRIBE_PAD
    total = _duration(video)
    segments, words = [], []
    boundary, i = 0.0, 0
    while boundary < total:
        last = boundary + chunk_sec >= total
        ss = max(0.0, boundary - pad)
        length = (chunk_sec + pad) + (boundary - ss)
        mp3 = workdir / f"chunk{i}.mp3"
        _run(["ffmpeg", "-y", "-ss", str(ss), "-t", str(length), "-i", str(video),
              "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", str(mp3)])
        j = _post_with_keys(mp3, keys).json()
        mp3.unlink(missing_ok=True)

        lo = boundary if i > 0 else 0.0
        hi = float("inf") if last else boundary + chunk_sec
        for sg in j.get("segments", []):
            st = sg["start"] + ss
            if lo - 0.01 <= st < hi:
                segments.append({"start": st, "end": sg["end"] + ss, "text": sg["text"].strip()})
        for w in j.get("words", []):
            st = w["start"] + ss
            if lo - 0.01 <= st < hi:
                words.append({"w": w["word"].strip(), "start": st, "end": w["end"] + ss})
        boundary += chunk_sec
        i += 1
    return segments, words


def _post_with_keys(mp3: Path, keys: list):
    """Sube un trozo probando las llaves una por una. Si una no tiene cupo (429) pasa a la siguiente;
    solo se rinde (y se usa Whisper local) cuando TODAS están sin cupo o rechazadas."""
    global _key_rr
    tried_wait = 0
    while True:
        live = [k for k in keys if k not in _key_dead]
        if not live:
            raise _UseLocal("todas las llaves de Groq fueron rechazadas")
        ready = [k for k in live if _key_cool.get(k, 0) <= time.time()]
        if not ready:
            wait = min(_key_cool[k] for k in live) - time.time()
            if wait <= 90 and tried_wait < 3:
                tried_wait += 1
                print(f"  Transcripción: todas las llaves en pausa, espero {int(wait) + 1} s…", flush=True)
                time.sleep(max(0.0, wait) + 1)
                continue
            raise _UseLocal(f"las {len(live)} llaves de Groq están sin cupo (la primera vuelve en ~{max(1, round(wait / 60))} min)")
        k0 = _key_rr % len(ready)
        _key_rr += 1
        for key in ready[k0:] + ready[:k0]:
            try:
                return _post_chunk(mp3, key)
            except _KeyBad as e:
                _key_dead.add(key)
                print(f"  Transcripción: llave …{key[-4:]} descartada ({e}).", flush=True)
            except _KeyBusy as e:
                _key_cool[key] = time.time() + e.wait
                print(f"  Transcripción: llave …{key[-4:]} sin cupo ({e}); pruebo la siguiente.", flush=True)
        # si ninguna de las listas funcionó, el ciclo vuelve a evaluar cuáles quedan


def _post_chunk(mp3: Path, key: str):
    """Sube un trozo con UNA llave. Lanza _KeyBad / _KeyBusy para que se pruebe otra, o _UseLocal si es la red/Groq."""
    import requests

    data = [
        ("model", "whisper-large-v3-turbo"),
        ("response_format", "verbose_json"),
        ("timestamp_granularities[]", "word"),
        ("timestamp_granularities[]", "segment"),
        ("language", config.LANGUAGE),
    ]
    prompt = config.whisper_prompt()
    if prompt:
        data.append(("prompt", prompt))
    try:
        with open(mp3, "rb") as f:
            r = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (mp3.name, f, "audio/mpeg")},
                data=data, timeout=600,
            )
    except requests.RequestException as e:
        raise _UseLocal(f"sin conexión: {type(e).__name__}")

    if r.ok:
        return r
    if r.status_code in (401, 403):
        raise _KeyBad(f"llave rechazada ({r.status_code})")
    if r.status_code in (402, 429):
        try:
            ra = float(r.headers.get("retry-after", ""))
        except ValueError:
            ra = None
        low = (r.text or "").lower()
        if _DAILY.search(low) or (ra is not None and ra > 600) or r.status_code == 402:
            raise _KeyBusy(min(ra if ra and ra > 600 else 3600, 6 * 3600), "se acabó el cupo del día")
        if _HOURLY.search(low):
            raise _KeyBusy(min((ra or 1800) + 1, 3600), "límite por hora")
        raise _KeyBusy(min((ra or 60) + 1, 600), "límite por minuto")
    if r.status_code >= 500:
        raise _UseLocal(f"Groq caído ({r.status_code})")
    raise RuntimeError(f"Groq transcripción {r.status_code}: {r.text[:200]}")
