"""Parte 4: audio y efectos del clip.

- Pitido en groserías (y el subtítulo sale censado: p***).
- Volumen parejo a -14 LUFS (el nivel que usan YouTube, Facebook e Instagram), en dos pasadas para que sea exacto.
- Zoom (punch-in) y cámara lenta en el momento de un disparo/explosión o en el pico de volumen.

Las funciones que deciden (find_profanity, choose_fx, make_tmap...) son puras: reciben listas y devuelven listas,
así se prueban sin video. Todo es opcional: si algo falla, el clip sale igual sin ese efecto.
"""
import json
import re
import subprocess
import unicodedata

import config

# ============================================================================= GROSERÍAS
# Se comparan palabras ENTERAS (ya sin acentos ni signos), nunca pedazos: "Singapur", "computadora", "vergüenza" o "ridículo"
# no se tocan. La ñ se conserva a propósito para no confundir "coño" con "cono" (un cono de tráfico).
_BAD = [
    r"mierd[aeo]s?", r"put[oa]s?", r"putit[oa]s?", r"putisim[oa]s?", r"hijueputa", r"hijoeputa", r"hijoputa", r"hdp",
    r"ping[ao]s?", r"coño", r"coños", r"cabron(?:a|es|as)?", r"carajos?", r"carajazo",
    r"jod(?:er|ido|ida|idos|idas|ete|iste|iendo|ienda)", r"vergas?", r"vergazo", r"pendej[oa]s?", r"culos?",
    r"mamaguev[oa]s?", r"guevos?", r"singa", r"singar", r"singao", r"singada", r"singado", r"puñeta", r"puñetas",
    r"puñetero", r"puñetera", r"cojones", r"chinga", r"chingar", r"chingada", r"chingado", r"chingaste",
    r"maricon(?:es)?", r"gilipollas", r"malparid[oa]s?", r"gonorrea",
    r"fuck", r"fucking", r"fucker", r"fucked", r"motherfucker", r"shit", r"shitty", r"bitch", r"bitches", r"asshole", r"dick",
]
_BAD_RE = re.compile("|".join(f"(?:{p})" for p in _BAD))

PAD_BEFORE = 0.06     # Whisper no clava el inicio de la palabra: se tapa un poco antes y un poco después
PAD_AFTER = 0.10
MIN_BEEP = 0.28
BEEP_LEVEL = 0.22     # volumen del pitido (1.0 = máximo); ~ -13 dBFS, se oye sin asustar


def norm_word(text):
    """'¡Coño!' -> 'coño', 'Mamagüevo' -> 'mamaguevo'. Quita acentos y signos, conserva la ñ."""
    t = str(text or "").lower().replace("ñ", "\u0001")
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").replace("\u0001", "ñ")
    return re.sub(r"[^a-zñ]", "", t)


def _word_list(raw):
    return {norm_word(x) for x in re.split(r"[,;\n]+", raw or "") if norm_word(x)}


def is_profane(word, extra=None, keep=None):
    n = norm_word(word)
    if not n:
        return False
    keep = _word_list(config.BLEEP_KEEP) if keep is None else keep
    extra = _word_list(config.BLEEP_WORDS) if extra is None else extra
    if n in keep:
        return False
    return n in extra or bool(_BAD_RE.fullmatch(n))


def find_profanity(words, start, end, extra=None, keep=None):
    """[(t0, t1)] en segundos RELATIVOS al inicio del clip, una por grupo de groserías, con margen y fusionando las que quedan pegadas."""
    out = []
    dur = end - start
    for w in words:
        if w["end"] < start or w["start"] > end or not is_profane(w["w"], extra, keep):
            continue
        t0 = max(0.0, w["start"] - start - PAD_BEFORE)
        t1 = min(dur, w["end"] - start + PAD_AFTER)
        if t1 - t0 < MIN_BEEP:
            t1 = min(dur, t0 + MIN_BEEP)
        if t1 > t0:
            out.append([t0, t1])
    out.sort()
    merged = []
    for a, b in out:
        if merged and a - merged[-1][1] < 0.12:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return [(round(a, 3), round(b, 3)) for a, b in merged]


def censor_words(words, extra=None, keep=None):
    """Copia de las palabras con las groserías censuradas para los subtítulos: 'puta' -> 'p***'."""
    out = []
    for w in words:
        if is_profane(w["w"], extra, keep):
            raw = str(w["w"])
            core = re.sub(r"[^\wñÑáéíóúÁÉÍÓÚüÜ]", "", raw)
            if core:
                stars = core[0] + "*" * max(2, len(core) - 1)
                w = {**w, "w": raw.replace(core, stars, 1)}
        out.append(w)
    return out


# ============================================================================= VOLUMEN
def measure_loudness(source, start, dur, target=None, timeout=300):
    """Primera pasada de loudnorm sobre el tramo del clip. Devuelve dict con las medidas o None si no se pudo (silencio, error)."""
    target = config.CLIP_LUFS if target is None else target
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(source), "-vn",
           "-af", f"loudnorm=I={target}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:  # noqa: BLE001
        return None
    return parse_loudnorm(r.stderr)


def parse_loudnorm(stderr):
    m = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m[-1])
        vals = {k: float(d[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")}
    except (ValueError, KeyError):
        return None
    if any(v != v or abs(v) == float("inf") for v in vals.values()) or vals["input_i"] < -60:   # silencio: nada que normalizar
        return None
    return vals


def loudnorm_filter(measured=None, target=None):
    """Filtro de loudnorm. Con medidas = lineal y exacto (2 pasadas); sin medidas = dinámico (1 pasada, menos exacto)."""
    t = config.CLIP_LUFS if target is None else target
    base = f"loudnorm=I={t}:TP=-1.5:LRA=11"
    if not measured:
        return base
    return (f"{base}:measured_I={measured['input_i']:.2f}:measured_TP={measured['input_tp']:.2f}:"
            f"measured_LRA={measured['input_lra']:.2f}:measured_thresh={measured['input_thresh']:.2f}:"
            f"offset={measured['target_offset']:.2f}:linear=true")


# ============================================================================= ZOOM Y CÁMARA LENTA
def _mode(*vals):
    """Primer valor que no sea 'auto'/None. Devuelve True/False/None (None = decide el perfil)."""
    for v in vals:
        if v is None:
            continue
        s = str(v).strip().lower()
        if s in ("", "auto"):
            continue
        return s in ("1", "true", "yes", "on", "si", "sí")
    return None


def wants(prof, opts=None):
    """(zoom, slow) que se deben intentar para este clip. Opciones de la web > .env > perfil."""
    opts = opts or {}
    fx = (prof or {}).get("fx") or {}
    zoom = _mode(opts.get("zoom"), config.CLIP_ZOOM)
    slow = _mode(opts.get("slowmo"), config.CLIP_SLOWMO)
    return (bool(fx.get("zoom")) if zoom is None else zoom), (bool(fx.get("slow")) if slow is None else slow)


def choose_fx(impacts, dur, peak=None, want_zoom=True, want_slow=True, rate=None):
    """Decide los efectos de UN clip.
    impacts = [(segundo, 'shot'|'boom')] relativos al clip; peak = (segundo, dB sobre lo normal) del momento más fuerte.
    Devuelve {'slow': (a, b, rate) | None, 'zoom': [(t0, t1, cantidad)]} o None si no hay nada que hacer.
    Reglas: máximo UNA cámara lenta y UN zoom; nada en los primeros 2 s (el gancho) ni en los últimos 2.5 s (el remate);
    la cámara lenta solo sobre una explosión (algo que se disfruta despacio), el zoom también sobre una ráfaga de disparos."""
    rate = min(0.9, max(0.5, float(rate if rate is not None else config.CLIP_SLOW_RATE)))
    if dur < 8 or not (want_zoom or want_slow):
        return None
    lo, hi = 2.0, dur - 2.5
    slow, zoom = None, []
    booms = [t for t, k in impacts if k == "boom" and lo <= t <= hi]
    if want_slow and booms:
        a = max(lo - 0.25, booms[0] - 0.25)
        slow = (round(a, 3), round(a + 1.2, 3), rate)
    if want_zoom:
        if slow:
            zoom = [(slow[0], slow[1], 0.10)]
        else:
            shots = [t for t, k in impacts if k in ("shot", "boom") and lo <= t <= hi]
            # ráfaga = al menos 3 impactos en 2.5 s
            burst = next((t for i, t in enumerate(shots) if sum(1 for u in shots[i:] if u - t <= 2.5) >= 3), None)
            if burst is not None:
                zoom = [(round(burst - 0.1, 3), round(burst + 0.9, 3), 0.10)]
            elif booms:
                zoom = [(round(booms[0] - 0.1, 3), round(booms[0] + 0.9, 3), 0.10)]
            elif peak and lo <= peak[0] <= hi and peak[1] >= 6.0:
                zoom = [(round(peak[0] - 0.15, 3), round(peak[0] + 0.85, 3), 0.08)]
    if not slow and not zoom:
        return None
    return {"slow": slow, "zoom": zoom}


def make_tmap(slow):
    """Función que pasa un segundo del clip original al segundo del clip con cámara lenta (para que los subtítulos sigan en sintonía)."""
    if not slow:
        return lambda t: t
    a, b, rate = slow
    extra = (b - a) * (1.0 / rate - 1.0)

    def tmap(t):
        if t <= a:
            return t
        if t <= b:
            return a + (t - a) / rate
        return t + extra
    return tmap


def out_duration(dur, slow):
    return dur + ((slow[1] - slow[0]) * (1.0 / slow[2] - 1.0) if slow else 0.0)


def zoom_chain(zooms, w=1080, h=1920):
    """Cadena de filtros de video para el zoom: sube rápido (0.15 s), se sostiene y baja suave (0.3 s). Termina con coma."""
    if not zooms:
        return ""
    z = "+".join(f"{amt:.3f}*clip(min((t-{t0:.3f})/0.15,({t1:.3f}-t)/0.3),0,1)" for t0, t1, amt in zooms)
    return (f"scale=w='trunc({w}*(1+{z})/2)*2':h='trunc({h}*(1+{z})/2)*2':eval=frame:flags=bicubic,"
            f"crop={w}:{h},setsar=1,")


def slow_video(src, dst, slow):
    """Tres tramos (antes / lento / después) pegados con concat. Devuelve el grafo con etiquetas [src] -> [dst]."""
    a, b, rate = slow
    return (f"[{src}]split=3[z0][z1][z2];"
            f"[z0]trim=start=0:end={a:.3f},setpts=PTS-STARTPTS[w0];"
            f"[z1]trim=start={a:.3f}:end={b:.3f},setpts=(PTS-STARTPTS)/{rate:.3f}[w1];"
            f"[z2]trim=start={b:.3f},setpts=PTS-STARTPTS[w2];"
            f"[w0][w1][w2]concat=n=3:v=1:a=0[{dst}]")


def audio_graph(dur, beeps=None, slow=None, loud=None, norm=False):
    """Grafo de audio de ffmpeg: entrada [0:a], salida [aout].
    beeps = [(t0, t1)] -> se silencia la voz y suena un pitido de 1 kHz; slow = (a, b, rate); norm=True -> loudnorm (loud = medidas)."""
    parts = ["[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo"]
    cur = None
    if beeps:
        gate = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in beeps)
        parts[0] += f",volume=volume=0:enable='{gate}'[m]"
        parts.append(f"aevalsrc='{BEEP_LEVEL}*sin(2*PI*1000*t)*gt({gate},0)':s=48000:d={dur:.3f},"
                     "aformat=sample_fmts=fltp:channel_layouts=stereo[bp]")
        parts.append("[m][bp]amix=inputs=2:duration=first:dropout_transition=0,volume=2[mx]")   # amix reparte 1/2 a cada entrada: volume=2 lo compensa
        cur = "mx"
    else:
        parts[0] += "[mx]"
        cur = "mx"
    if slow:
        a, b, rate = slow
        parts.append(f"[{cur}]asplit=3[x0][x1][x2]")
        parts.append(f"[x0]atrim=start=0:end={a:.3f},asetpts=PTS-STARTPTS[y0]")
        parts.append(f"[x1]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,atempo={rate:.3f}[y1]")
        parts.append(f"[x2]atrim=start={b:.3f},asetpts=PTS-STARTPTS[y2]")
        parts.append("[y0][y1][y2]concat=n=3:v=0:a=1[sl]")
        cur = "sl"
    tail = []
    if norm:
        tail.append(loudnorm_filter(loud))
        tail.append("aresample=48000")
    parts.append(f"[{cur}]{','.join(tail) if tail else 'anull'}[aout]")
    return ";".join(parts)


# ============================================================================= ANÁLISIS DEL TRAMO (para decidir el efecto)
def analyze_clip_audio(source, start, dur):
    """Lee SOLO el audio del clip y devuelve (impactos [(s, tipo)], pico (s, dB sobre lo normal) | None). Vacío si falla."""
    try:
        import numpy as np

        import detect
    except ImportError:
        return [], None
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(source), "-vn", "-ac", "1",
           "-ar", str(detect.RATE), "-f", "s16le", "-"]
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=120).stdout
        a = np.frombuffer(raw[: len(raw) // 2 * 2], np.int16).astype(np.float32) / 32768.0
        if len(a) < detect.RATE * 3:
            return [], None
        imp = detect.impacts_from_features(*detect.impact_features(a), lookahead=60)
        hop = detect.RATE // 4                                      # medio segundo / 2 = ventanas de 0.25 s
        n = len(a) // hop
        rms = np.sqrt((a[: n * hop].reshape(n, hop) ** 2).mean(axis=1) + 1e-12)
        db = 20 * np.log10(rms)
        i = int(np.argmax(db))
        peak = (float((i + 0.5) * hop / detect.RATE), float(db[i] - np.median(db)))
        return [(float(t), k) for t, k in imp], peak
    except Exception:  # noqa: BLE001
        return [], None


def plan_fx(source, start, dur, prof, opts=None):
    """Efectos de este clip o None. Solo lee el audio del tramo (rápido) y solo si el perfil o el .env piden zoom/cámara lenta."""
    zoom, slow = wants(prof, opts)
    if not (zoom or slow):
        return None
    impacts, peak = analyze_clip_audio(source, start, dur)
    return choose_fx(impacts, dur, peak, want_zoom=zoom, want_slow=slow)


def has_audio(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=index", "-of", "csv=p=0",
                            str(path)], capture_output=True, text=True, timeout=60)
        return bool(r.stdout.strip())
    except Exception:  # noqa: BLE001
        return False
