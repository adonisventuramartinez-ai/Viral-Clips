"""Ritmo: quita silencios largos y muletillas ("eh", "mmm") de un clip y mete un zoom suave en cada corte para que no se note el salto.

Todo es opcional y falla sin romper el clip: si algo sale mal, render_clip sigue con el tramo original.

  plan_cuts(words, start, end)  -> lista de tramos [(a, b)] que se QUEDAN (lógica pura, con pruebas)
  apply(source, words, start, end, workdir, stem) -> (video_nuevo, palabras_nuevas, duración, zooms) o None
"""
import re
import subprocess
import unicodedata
from pathlib import Path

import config

# Muletillas puras. NO se incluyen palabras con significado ("este", "o sea", "ah", "oh", "uh-huh") para no cambiar lo que dice la persona.
FILLERS = {"eh", "ehh", "ehhh", "em", "emm", "emmm", "mm", "mmm", "mmmm", "hmm", "hm", "ee", "eee", "aam", "am", "umm", "um", "uh"}

GAP_MIN = 0.65      # una pausa más larga que esto se acorta
PAUSE_KEEP = 0.30   # cuánto de la pausa se deja (respiro natural)
LEAD_KEEP = 0.15    # silencio que se deja antes de la primera palabra
TAIL_KEEP = 0.35    # silencio que se deja después de la última palabra
MIN_KEEP = 0.25     # un tramo que se queda nunca dura menos que esto (evita cortar palabras sueltas)
MAX_CUT_FRAC = 0.30  # nunca se quita más del 30 % del clip
MIN_SAVED = 0.6     # si el ahorro total es menor, no vale la pena recodificar
FADE = 0.02         # fundido de 20 ms en cada corte (evita el "clic" de audio)
PUNCH = 0.06        # zoom del "punch-in" alterno
PUNCH_MIN_SEG = 1.0  # solo hay zoom en tramos de al menos 1 s
PUNCH_FROM = 2.0    # el gancho (primeros 2 s) no se toca
MAX_PUNCH = 8


def norm(text):
    t = unicodedata.normalize("NFD", str(text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z]", "", t)


def is_filler(word):
    return norm(word) in FILLERS


def plan_cuts(words, start, end, gap=GAP_MIN, max_frac=MAX_CUT_FRAC):
    """Devuelve (keeps, dropped_idx): keeps = [(a, b)] tramos del clip que se quedan, en segundos del VIDEO FUENTE;
    dropped_idx = índices de `words` que se eliminan (muletillas). Devuelve (None, set()) si no vale la pena."""
    ws = [(i, w) for i, w in enumerate(words) if w["start"] >= start - 0.05 and w["end"] <= end + 0.3]
    if len(ws) < 6 or end - start < 8:
        return None, set()
    dropped = {i for i, w in ws if is_filler(w["w"])}
    spoken = [(i, w) for i, w in ws if i not in dropped]
    if len(spoken) < 5:
        return None, set()

    cand = []   # (a, b) trozos que se QUITAN
    first, last = spoken[0][1], spoken[-1][1]
    if first["start"] - start > LEAD_KEEP + 0.25:
        cand.append((start, first["start"] - LEAD_KEEP))
    if end - last["end"] > TAIL_KEEP + 0.4:
        cand.append((last["end"] + TAIL_KEEP, end))
    for (_, a), (_, b) in zip(spoken, spoken[1:]):
        if b["start"] - a["end"] > gap:
            half = PAUSE_KEEP / 2
            cand.append((a["end"] + half, b["start"] - half))
    for i in sorted(dropped):
        w = words[i]
        cand.append((max(start, w["start"] - 0.02), min(end, w["end"] + 0.04)))

    # nunca más del max_frac del clip: se quedan los recortes más largos primero
    cand.sort(key=lambda c: -(c[1] - c[0]))
    budget, picked = max_frac * (end - start), []
    for a, b in cand:
        if b - a <= 0.02 or b - a > budget:
            continue
        budget -= b - a
        picked.append((a, b))
    picked.sort()

    # junta cortes pegados y exige que cada tramo que se queda dure al menos MIN_KEEP
    merged = []
    for a, b in picked:
        if merged and a - merged[-1][1] < MIN_KEEP:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    keeps, pos = [], start
    for a, b in merged:
        if a - pos > 0.05:   # los tramos del medio ya miden >= MIN_KEEP (los cortes pegados se unieron arriba)
            keeps.append((pos, a))
        pos = b
    if end - pos > 0.05:
        keeps.append((pos, end))
    saved = (end - start) - sum(b - a for a, b in keeps)
    if saved < MIN_SAVED or not keeps:
        return None, set()
    return keeps, dropped


def remap(keeps):
    """Función: segundo del video fuente -> segundo del clip nuevo (None si cae en un tramo quitado)."""
    spans, acc = [], 0.0
    for a, b in keeps:
        spans.append((a, b, acc))
        acc += b - a

    def f(t):
        for a, b, off in spans:
            if a - 1e-6 <= t <= b + 1e-6:
                return off + (t - a)
        return None
    return f


def new_words(words, keeps, dropped, start, end):
    """Palabras del clip con tiempos nuevos, medidos desde 0 en el video recortado."""
    m = remap(keeps)
    out = []
    for i, w in enumerate(words):
        if i in dropped or w["start"] < start - 0.05 or w["end"] > end + 0.3:
            continue
        a, b = m(w["start"]), m(min(w["end"], end))
        if a is None:
            continue
        x = dict(w)
        x["start"], x["end"] = a, (b if b is not None and b > a else a + 0.1)
        out.append(x)
    return out


def punch_zooms(keeps):
    """Zoom suave en cada segundo tramo (1.º sin zoom, 2.º con zoom, ...): oculta el salto del corte. [(t0, t1, cantidad)]"""
    zooms, acc = [], 0.0
    for i, (a, b) in enumerate(keeps):
        d = b - a
        if i % 2 == 1 and d >= PUNCH_MIN_SEG and acc >= PUNCH_FROM:
            zooms.append((round(acc, 3), round(acc + d, 3), PUNCH))
        acc += d
    return zooms[:MAX_PUNCH]


def _cut(source, keeps, start, out, has_audio):
    """ffmpeg: une los tramos que se quedan con un fundido de 20 ms en el audio. Tiempos relativos a `start`."""
    v, a = [], []
    for i, (x, y) in enumerate(keeps):
        x, y = x - start, y - start
        v.append(f"[0:v]trim=start={x:.3f}:end={y:.3f},setpts=PTS-STARTPTS[v{i}]")
        if has_audio:
            d = y - x
            a.append(f"[0:a]atrim=start={x:.3f}:end={y:.3f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d={FADE},afade=t=out:st={max(0.0, d - FADE):.3f}:d={FADE}[a{i}]")
    n = len(keeps)
    pads = "".join(f"[v{i}]" + (f"[a{i}]" if has_audio else "") for i in range(n))
    graph = ";".join(v + a) + f";{pads}concat=n={n}:v=1:a={1 if has_audio else 0}[v]" + ("[a]" if has_audio else "")
    dur = keeps[-1][1] - start + 1
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(Path(source).resolve()),
           "-filter_complex", graph, "-map", "[v]"] + (["-map", "[a]"] if has_audio else [])
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "12", "-pix_fmt", "yuv420p"]
    cmd += (["-c:a", "aac", "-b:a", "256k"] if has_audio else ["-an"]) + [str(Path(out).resolve())]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if r.returncode != 0 or not Path(out).exists():
        raise RuntimeError("ffmpeg: " + r.stderr[-300:])
    return out


def apply(source, words, start, end, workdir, stem):
    """Recorta silencios y muletillas. Devuelve (video_nuevo, palabras, duración, zooms) o None si no hace falta / falla."""
    try:
        import postfx
        keeps, dropped = plan_cuts(words, start, end)
        if not keeps:
            return None
        out = Path(workdir) / f"{stem}_tight.mp4"
        _cut(source, keeps, start, out, postfx.has_audio(source))
        nw = new_words(words, keeps, dropped, start, end)
        dur = sum(b - a for a, b in keeps)
        saved = (end - start) - dur
        print(f"  Ritmo: quité {saved:.1f} s de silencios/muletillas ({len(keeps) - 1} corte(s), {len(dropped)} muletilla(s))", flush=True)
        return out, nw, dur, punch_zooms(keeps)
    except Exception as e:  # noqa: BLE001
        print(f"  Ritmo: no pude recortar ({type(e).__name__}: {str(e)[:100]}); sigo sin recortar.", flush=True)
        return None
