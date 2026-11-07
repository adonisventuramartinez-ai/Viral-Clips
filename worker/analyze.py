"""La IA elige los momentos virales a partir de la transcripción (con rotación de proveedores en llm.py)."""
import json
import math

import config
import llm

WINDOW = 900  # segundos de transcripción por llamada

PROMPT = """Eres editor experto de clips virales para TikTok, Reels y Shorts.
Te paso un trozo de la transcripción de un podcast/directo. Cada línea empieza con [segundo].

Elige hasta {want} momentos con alto potencial viral: polémica, humor, confesiones, historias con gancho,
frases citables, reacciones fuertes, giros inesperados. Cada clip debe:
- durar cerca de {secs} segundos (entre {lo} y {hi});
- empezar con un gancho que enganche en los primeros 3 segundos;
- terminar al cerrar una idea completa;
- entenderse solo, sin contexto previo.

Usa EXACTAMENTE los segundos de las marcas [..] para start y end.
Responde SOLO con JSON, sin texto extra:
{{"moments":[{{"start":<seg>,"end":<seg>,"title":"título corto y llamativo (máx 70 car.)","score":<0-100 probabilidad viral>,"reason":"por qué funciona, 1 frase"}}]}}

TRANSCRIPCIÓN:
{text}
"""


def _chunks(segments):
    out, cur, t0 = [], [], None
    for s in segments:
        if t0 is None:
            t0 = s["start"]
        if s["start"] - t0 > WINDOW and cur:
            out.append(cur)
            cur, t0 = [], s["start"]
        cur.append(s)
    if cur:
        out.append(cur)
    return out


def _parse_moments(txt):
    """Devuelve la lista de momentos, o None si la respuesta no es un JSON válido (para probar otro proveedor)."""
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b < 0:
        return None
    try:
        data = json.loads(txt[a : b + 1])
    except json.JSONDecodeError:
        return None
    moments = data.get("moments") if isinstance(data, dict) else None
    return moments if isinstance(moments, list) else None


def _build_prompt(chunk, want, secs):
    text = "\n".join(f"[{int(s['start'])}] {s['text']}" for s in chunk)
    return PROMPT.format(want=want, secs=secs, lo=int(secs * 0.6), hi=int(secs * 1.5), text=text)


def _ask_llm(chunk, want, secs):
    """Pregunta a la IA. Si un proveedor se queda sin cupo, llm.py pasa solo al siguiente."""
    return llm.ask(_build_prompt(chunk, want, secs), check=_parse_moments)


def _overlap(a, b):
    inter = max(0.0, min(a["end"], b["end"]) - max(a["start"], b["start"]))
    return inter / max(1e-6, min(a["end"] - a["start"], b["end"] - b["start"]))


def select_moments(candidates, n_clips):
    """Quita solapes y se queda con los mejores. Devuelve (elegidos, descartados)."""
    ranked = sorted(candidates, key=lambda m: m["score"], reverse=True)
    chosen, rejected = [], []
    for m in ranked:
        if len(chosen) >= n_clips:
            rejected.append({"title": m["title"], "score": m["score"],
                             "reason": f"Quedó fuera del top {n_clips}"})
        elif any(_overlap(m, c) > 0.3 for c in chosen):
            rejected.append({"title": m["title"], "score": m["score"],
                             "reason": "Ese momento o tema ya tiene clip"})
        else:
            chosen.append(m)
    return chosen, rejected


def _clean(m, secs, duration):
    try:
        start, end = float(m["start"]), float(m["end"])
        score = int(max(0, min(100, float(m.get("score", 50)))))
    except (KeyError, TypeError, ValueError):
        return None
    if end <= start:
        end = start + secs
    length = min(max(end - start, secs * 0.5), secs * 1.8)
    end = min(start + length, duration)
    if end - start < 5:
        return None
    return {"start": start, "end": end, "score": score,
            "title": str(m.get("title", "Clip"))[:80], "reason": str(m.get("reason", ""))}


def find_moments(segments, n_clips, secs):
    duration = segments[-1]["end"] if segments else 0
    chunks = _chunks(segments)
    want = max(3, math.ceil(n_clips * 1.6 / max(1, len(chunks))))
    cands = []
    for ch in chunks:
        for m in _ask_llm(ch, want, secs):
            c = _clean(m, secs, duration)
            if c:
                cands.append(c)
    return select_moments(cands, n_clips)


def review_window(segments, secs, existing, duration, min_score=None, max_new=2):
    """Revisión en vivo: mira la ventana reciente y devuelve (nuevos_clips, descartados).

    existing = clips ya creados (para no repetir el mismo momento).
    duration = hasta dónde hay transcripción (ningún clip puede pasarse de ahí).
    """
    min_score = config.LIVE_MIN_SCORE if min_score is None else min_score
    cands = []
    for ch in _chunks(segments):
        for m in _ask_llm(ch, 4, secs):
            c = _clean(m, secs, duration)
            if c:
                cands.append(c)
    chosen, rejected = [], []
    for m in sorted(cands, key=lambda x: x["score"], reverse=True):
        if any(_overlap(m, c) > 0.3 for c in existing + chosen):
            rejected.append({"title": m["title"], "score": m["score"], "reason": "Ese momento o tema ya tiene clip"})
        elif m["score"] < min_score:
            rejected.append({"title": m["title"], "score": m["score"], "reason": f"Puntaje bajo (mínimo {min_score})"})
        elif len(chosen) >= max_new:
            rejected.append({"title": m["title"], "score": m["score"], "reason": f"Ya se eligieron {max_new} mejores en esta revisión"})
        else:
            chosen.append(m)
    return chosen, rejected
