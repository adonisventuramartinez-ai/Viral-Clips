"""Claude elige los momentos virales a partir de la transcripción."""
import json
import math
import time

import config

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


def _parse_json(txt):
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b < 0:
        return {"moments": []}
    try:
        return json.loads(txt[a : b + 1])
    except json.JSONDecodeError:
        return {"moments": []}


def _build_prompt(chunk, want, secs):
    text = "\n".join(f"[{int(s['start'])}] {s['text']}" for s in chunk)
    return PROMPT.format(want=want, secs=secs, lo=int(secs * 0.6), hi=int(secs * 1.5), text=text)


def _ask_anthropic(prompt):
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=config.CLAUDE_MODEL, max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _ask_groq(prompt, retries=5):
    """Llama en Groq (gratis). Reintenta si choca con el límite por minuto (429)."""
    import requests

    for attempt in range(retries):
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            json={
                "model": config.GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 3000,
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        if r.status_code == 429:
            time.sleep(float(r.headers.get("retry-after", 15)) + 1)
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise RuntimeError("Groq: límite de uso alcanzado, intenta de nuevo en unos minutos")


def _ask_llm(chunk, want, secs):
    prompt = _build_prompt(chunk, want, secs)
    raw = _ask_anthropic(prompt) if config.LLM_PROVIDER == "anthropic" else _ask_groq(prompt)
    return _parse_json(raw).get("moments", [])


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
