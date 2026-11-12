"""Pistas extra para que la IA elija mejor: picos de volumen (gritos, risas fuertes) y, en VODs de Twitch,
explosiones del chat. Se marcan en la transcripción con 🔊 y 💬 y suben un poco el puntaje de esos momentos."""
import json
import math
import statistics
import subprocess
from pathlib import Path

RATE = 8000


def loud_seconds(video: Path, min_db_over=6.0, z=2.2, max_minutes=240) -> set:
    """Segundos (enteros, relativos al video) con volumen claramente por encima de lo normal. Vacío si falla."""
    try:
        import numpy as np
    except ImportError:
        return set()
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(RATE), "-t", str(max_minutes * 60),
           "-f", "s16le", "-"]
    levels = []
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        size = RATE * 2
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            a = np.frombuffer(buf, np.int16).astype(np.float32)
            levels.append(20 * math.log10(float(np.sqrt(np.mean(a * a))) + 1.0))
        p.stdout.close()
        p.wait()
    except Exception:  # noqa: BLE001
        return set()
    if len(levels) < 20:
        return set()
    # suaviza 2 s para que un golpe suelto no cuente
    sm = [statistics.fmean(levels[max(0, i - 1): i + 2]) for i in range(len(levels))]
    med = statistics.median(sm)
    mad = statistics.median(abs(x - med) for x in sm) * 1.4826 or 1.0
    return {i for i, x in enumerate(sm) if x - med >= min_db_over and (x - med) / mad >= z}


def _find_times(node, out):
    if isinstance(node, dict):
        if "content_offset_seconds" in node:
            try:
                out.append(float(node["content_offset_seconds"]))
            except (TypeError, ValueError):
                pass
        for v in node.values():
            _find_times(v, out)
    elif isinstance(node, list):
        for v in node:
            _find_times(v, out)


def chat_seconds(url: str, workdir: Path, offset: float, duration: float, bin_s=10, z=2.0) -> set:
    """Solo VODs de Twitch. Baja el chat (yt-dlp, subtítulo 'rechat') y marca los trozos de 10 s con muchísimos
    mensajes. Es una ayuda opcional: si algo falla devuelve vacío y todo sigue igual."""
    if "twitch.tv" not in (url or "") or "/videos/" not in url:
        return set()
    try:
        import yt_dlp
        opts = {"quiet": True, "skip_download": True, "writesubtitles": True, "subtitleslangs": ["rechat"],
                "outtmpl": str(workdir / "chat.%(ext)s")}
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([url])
        times = []
        for f in workdir.glob("chat*"):
            if f.suffix in (".json", ".rechat") or "rechat" in f.name:
                _find_times(json.loads(f.read_text(encoding="utf-8", errors="ignore")), times)
        times = [t - offset for t in times if 0 <= t - offset <= duration]
        if len(times) < 50:
            return set()
        bins = [0] * (int(duration // bin_s) + 1)
        for t in times:
            bins[int(t // bin_s)] += 1
        med = statistics.median(bins)
        mad = statistics.median(abs(x - med) for x in bins) * 1.4826 or 1.0
        hot = set()
        for i, c in enumerate(bins):
            if c >= med * 2 and (c - med) / mad >= z:
                hot.update(range(i * bin_s, (i + 1) * bin_s))
        print(f"  Chat: {len(times)} mensajes, {len(hot) // bin_s} momento(s) donde explotó", flush=True)
        return hot
    except Exception as e:  # noqa: BLE001
        print(f"  Chat: no pude leerlo ({type(e).__name__}); sigo sin esa pista.", flush=True)
        return set()


def annotate(segments, loud: set, chat: set):
    """Marca cada frase: s['hot'] = '🔊', '💬' o ambos (vacío si nada). Devuelve cuántas marcó."""
    n = 0
    for s in segments:
        a, b = int(s["start"]), int(math.ceil(s["end"]))
        marks = ""
        if loud and any(t in loud for t in range(a, b + 1)):
            marks += "🔊"
        if chat and any(t in chat for t in range(a, b + 1)):
            marks += "💬"
        s["hot"] = marks
        n += bool(marks)
    return n
