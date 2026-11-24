"""Ajusta el inicio y el fin de un momento para que no corte a media frase.

Usa los tiempos de cada palabra (words) para encontrar finales de frase y pausas. Si la entrevista lo pide,
sube el inicio hasta la pregunta que provocó la respuesta. Todo son funciones puras (fáciles de probar).
"""
import re

SENT_END = re.compile(r"[.!?…]+[\"')\]»”]*$")
PAUSE = 0.35         # silencio entre palabras que cuenta como pausa
SENT_GAP = 0.75      # silencio tan largo que equivale a final de frase
MIN_LEN = 5.0


def boundaries(words):
    """(inicios_de_frase, finales_de_frase, inicios_tras_pausa, finales_antes_de_pausa) en segundos."""
    s_starts, s_ends, p_starts, p_ends = [], [], [], []
    n = len(words)
    for i, w in enumerate(words):
        if i == 0:
            s_starts.append(w["start"])
        nxt = words[i + 1] if i + 1 < n else None
        gap = (nxt["start"] - w["end"]) if nxt else 99.0
        text = str(w.get("w", "")).strip()
        if SENT_END.search(text) or gap >= SENT_GAP:
            s_ends.append(w["end"])
            if nxt:
                s_starts.append(nxt["start"])
        if nxt and gap >= PAUSE:
            p_ends.append(w["end"])
            p_starts.append(nxt["start"])
    return s_starts, s_ends, p_starts, p_ends


def _nearest(cands, t, before, after, prefer_before=True):
    """Candidato en [t-before, t+after] con menor costo; los del lado preferido cuestan menos."""
    best, best_cost = None, None
    for c in cands:
        if c < t - before or c > t + after:
            continue
        d = abs(c - t)
        on_pref = (c <= t) if prefer_before else (c >= t)
        cost = d if on_pref else d * 1.4
        if best is None or cost < best_cost:
            best, best_cost = c, cost
    return best


def snap_start(t, words, bounds=None):
    s_starts, _e, p_starts, _pe = bounds or boundaries(words)
    c = _nearest(s_starts, t, 5.0, 3.0, prefer_before=True)
    if c is None:
        c = _nearest(p_starts, t, 2.0, 2.0, prefer_before=True)
    if c is None:   # al menos no empezar a media palabra
        inside = [w for w in words if w["start"] <= t <= w["end"]]
        c = inside[0]["start"] if inside else t
    return c


def snap_end(t, start, words, max_len, bounds=None):
    _s, s_ends, _ps, p_ends = bounds or boundaries(words)
    limit = start + max_len
    c = _nearest([x for x in s_ends if x <= limit], t, 6.0, 8.0, prefer_before=False)
    if c is None:
        c = _nearest([x for x in p_ends if x <= limit], t, 3.0, 3.0, prefer_before=False)
    if c is None:
        inside = [w for w in words if w["start"] <= t <= w["end"]]
        c = inside[0]["end"] if inside else t
    return min(c, limit)


def include_question(start, segments, max_back=25.0):
    """Si justo antes del inicio hay una pregunta, devuelve el inicio de esa pregunta (si no, el mismo inicio)."""
    prev = None
    for s in segments:
        if s["start"] >= start:
            break
        if s["end"] >= start - 8.0:
            prev = s
    if prev and str(prev.get("text", "")).strip().endswith("?") and 0 < start - prev["start"] <= max_back:
        return prev["start"]
    return start


def snap_moment(m, words, segments, secs, profile, duration):
    """Devuelve una copia del momento con inicio/fin ajustados. Si no hay palabras, lo deja igual."""
    out = dict(m)
    if not words:
        return out
    b = boundaries(words)
    max_len = secs * 1.6
    start = snap_start(m["start"], words, b)
    if profile.get("question"):
        start = include_question(start, segments)
    start = max(0.0, start - float(profile.get("preroll", 0.0)))
    end = snap_end(m["end"], start, words, max_len, b) + float(profile.get("tail", 0.4))
    end = min(end, duration, start + max_len)
    if end - start < MIN_LEN:       # el ajuste dejó el clip demasiado corto: se respeta lo que pidió la IA
        return out
    out["start"], out["end"] = start, end
    return out
