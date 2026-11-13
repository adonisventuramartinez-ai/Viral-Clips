"""Pistas extra para que la IA elija mejor: picos de volumen (gritos, risas fuertes) y, en VODs de Twitch,
explosiones del chat. Se marcan en la transcripción con 🔊 y 💬 y suben un poco el puntaje de esos momentos."""
import json
import math
import re
import statistics
import subprocess
from pathlib import Path

RATE = 8000
ACTION_TEXT = "[acción sin voz]"


def audio_levels(video: Path, max_minutes=240) -> list:
    """Volumen de cada segundo del video en dB (una lista, un valor por segundo). Vacía si falla."""
    try:
        import numpy as np
    except ImportError:
        return []
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
        return []
    return levels


def loud_from_levels(levels, min_db_over=6.0, z=2.2) -> set:
    """Segundos (índices de la lista) con volumen claramente por encima de lo normal."""
    if len(levels) < 20:
        return set()
    # suaviza 2 s para que un golpe suelto no cuente
    sm = [statistics.fmean(levels[max(0, i - 1): i + 2]) for i in range(len(levels))]
    med = statistics.median(sm)
    mad = statistics.median(abs(x - med) for x in sm) * 1.4826 or 1.0
    return {i for i, x in enumerate(sm) if x - med >= min_db_over and (x - med) / mad >= z}


def loud_seconds(video: Path, min_db_over=6.0, z=2.2, max_minutes=240) -> set:
    """Segundos (enteros, relativos al video) con volumen claramente por encima de lo normal. Vacío si falla."""
    return loud_from_levels(audio_levels(video, max_minutes), min_db_over, z)


def scene_levels(video: Path, max_minutes=240) -> list:
    """Cuánto cambia la imagen en cada segundo (0 = igual, 1 = otra escena). Usa 4 fotogramas por segundo, es barato.
    Devuelve una lista con un valor por segundo (promedio de los cambios de ese segundo). Vacía si falla."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-an", "-t", str(max_minutes * 60),
           "-vf", "fps=4,scale=160:-2,select=gte(scene\\,0),metadata=print:file=-", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=max_minutes * 60)
    except Exception:  # noqa: BLE001
        return []
    per = {}
    t = None
    for line in r.stdout.splitlines():
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([0-9.]+)", line)
        if m and t is not None:
            per.setdefault(int(t), []).append(float(m.group(1)))
    if not per:
        return []
    return [statistics.fmean(per.get(i, [0.0])) for i in range(max(per) + 1)]


def motion_from_levels(lv, min_score=0.05, z=2.5, min_over=0.03) -> set:
    """Segundos (índices de la lista) con un cambio de imagen claramente mayor al normal."""
    if len(lv) < 20:
        return set()
    sm = [statistics.fmean(lv[max(0, i - 1): i + 2]) for i in range(len(lv))]
    med = statistics.median(sm)
    mad = statistics.median(abs(x - med) for x in sm) * 1.4826 or 0.01
    return {i for i, x in enumerate(sm) if x >= min_score and x - med >= min_over and (x - med) / mad >= z}


def motion_seconds(video: Path, min_score=0.05, z=2.5, min_over=0.03) -> set:
    """Segundos con un cambio de imagen claramente mayor al normal (explosiones, jugadas, cortes bruscos)."""
    return motion_from_levels(scene_levels(video), min_score, z, min_over)


def add_action_markers(segments, loud: set, motion: set, chat: set = None, gap=3, min_gap_to_speech=1.5):
    """Para juegos: agrega líneas '[acción sin voz]' donde hubo picos (🔊/🎮/💬) pero nadie hablaba,
    para que la IA pueda elegir jugadas sin voz. Devuelve una lista NUEVA ordenada; no toca la transcripción guardada."""
    chat = chat or set()
    secs = sorted(loud | motion | chat)
    if not secs:
        return list(segments)
    groups, cur = [], [secs[0]]
    for t in secs[1:]:
        if t - cur[-1] <= gap:
            cur.append(t)
        else:
            groups.append(cur)
            cur = [t]
    groups.append(cur)
    out = list(segments)
    for g in groups:
        a, b = g[0], g[-1] + 1
        speech = any(s["end"] > a - min_gap_to_speech and s["start"] < b + min_gap_to_speech and s.get("text") != ACTION_TEXT
                     for s in segments)
        if speech:
            continue
        marks = ("🔊" if any(t in loud for t in g) else "") + ("🎮" if any(t in motion for t in g) else "") \
            + ("💬" if any(t in chat for t in g) else "")
        out.append({"start": float(a), "end": float(b), "text": ACTION_TEXT, "hot": marks})
    out.sort(key=lambda s: s["start"])
    return out


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


def hot_from_times(times, lo: float, hi: float, bin_s=10, z=2.0, min_msgs=6, baseline_s=600) -> set:
    """Chat en vivo: recibe los segundos (de la línea de tiempo de la grabación) en que llegó cada mensaje y devuelve los
    segundos de [lo, hi) donde el chat explotó. La referencia 'normal' son los últimos `baseline_s` segundos antes de hi.
    Un trozo de `bin_s` segundos cuenta si tiene al menos `min_msgs` mensajes, más del doble de lo normal y z robusto >= z."""
    if hi - lo < bin_s or not times:
        return set()
    base_lo = max(0.0, hi - baseline_s)
    first = int(base_lo // bin_s) * bin_s
    n = int((hi - first) // bin_s) + 1
    bins = [0] * n
    for t in times:
        if first <= t < hi:
            bins[int((t - first) // bin_s)] += 1
    if sum(bins) < 15:      # muy poco chat: no hay referencia confiable
        return set()
    med = statistics.median(bins)
    mad = statistics.median(abs(x - med) for x in bins) * 1.4826 or 1.0
    hot = set()
    for i, c in enumerate(bins):
        a = first + i * bin_s
        if a + bin_s <= lo or a >= hi:
            continue
        if c >= min_msgs and c >= med * 2 and (c - med) / mad >= z:
            hot.update(range(max(int(lo), a), min(int(hi), a + bin_s)))
    return hot


def annotate(segments, loud: set, chat: set, motion: set = None):
    """Marca cada frase: s['hot'] = '🔊' (volumen), '🎮' (acción en pantalla), '💬' (chat) o varios (vacío si nada).
    Devuelve cuántas marcó."""
    n = 0
    for s in segments:
        a, b = int(s["start"]), int(math.ceil(s["end"]))
        marks = ""
        if loud and any(t in loud for t in range(a, b + 1)):
            marks += "🔊"
        if motion and any(t in motion for t in range(a, b + 1)):
            marks += "🎮"
        if chat and any(t in chat for t in range(a, b + 1)):
            marks += "💬"
        s["hot"] = marks
        n += bool(marks)
    return n
