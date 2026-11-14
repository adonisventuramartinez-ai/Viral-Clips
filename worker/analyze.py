"""La IA elige los momentos virales a partir de la transcripción (con rotación de proveedores en llm.py).

Flujo: candidatos por trozos -> cortes ajustados a pausas/finales de frase -> pistas (volumen, acción, chat, palabras clave)
-> segunda pasada de la IA que re-puntúa todo junto -> quita solapes y se queda con los mejores.
"""
import json
import math
import re

import config
import detect
import llm
import profiles
import snap
import vision

WINDOW = 900  # segundos de transcripción por llamada

PROMPT = """Eres editor experto de clips virales para TikTok, Reels y Shorts.
Te paso un trozo de la transcripción de {kind}. Cada línea empieza con [segundo] y a veces con quién habla.
{guide}
{game_line}
Elige hasta {want} momentos (si hay muchos, ordénalos de mejor a peor y no repitas el mismo tema) con alto potencial viral.
Cada clip debe:
- durar cerca de {secs} segundos (entre {lo} y {hi});
- empezar con un gancho que enganche en los primeros 3 segundos;
- terminar al cerrar una idea completa;
- entenderse solo, sin contexto previo.

Las líneas con 🔊 tuvieron un pico de volumen (gritos, risas fuertes), las que tienen 🎮 un cambio brusco de imagen (acción en pantalla),
las que tienen 💬 hicieron explotar el chat, 💥 significa tiroteo o explosión detectados en el audio, 📺 una pantalla de juego
(WASTED, BUSTED, MISSION PASSED o estrellas de policía; el detalle va entre paréntesis) y 🗯 una discusión (varias personas hablando
fuerte y rápido). Son buenas pistas de que pasó algo, pero decide tú por el contenido.
Usa EXACTAMENTE los segundos de las marcas [..] para start y end.
Responde SOLO con JSON, sin texto extra:
{{"moments":[{{"start":<seg>,"end":<seg>,"title":"título corto y llamativo (máx 70 car.)","hook":"frase gancho de 3 a 7 palabras que sale arriba del clip al empezar (provoca curiosidad, sin spoilear)","score":<0-100 probabilidad viral>,"reason":"por qué funciona, 1 frase","description":"descripción para redes, 1 o 2 frases con gancho","hashtags":["#tema1","#tema2","#tema3","#tema4","#tema5"]}}]}}

TRANSCRIPCIÓN:
{text}
"""

RERANK_PROMPT = """Eres el editor jefe de un canal de clips virales. Abajo hay {n} clips candidatos del MISMO video, cada uno con su texto.
Puntúa de 0 a 100 qué tan probable es que cada uno se haga viral por sí solo: gancho en los primeros 3 segundos, se entiende sin contexto,
cierre completo y emoción. Sé exigente y usa todo el rango; si dos candidatos tratan lo mismo, al menos bueno ponle menos puntos.
{guide}
Responde SOLO con JSON: {{"scores":[{{"i":<número del candidato>,"score":<0-100>}}]}}

CANDIDATOS:
{items}
"""

from energy import ACTION_TEXT  # noqa: E402


# ----------------------------------------------------------------------------- utilidades
def _chunks(segments):
    """Ventanas de ~WINDOW segundos que se solapan ANALYSIS_OVERLAP segundos (90 por defecto):
    un momento que cae en el borde entre dos ventanas aparece completo en una de las dos.
    Los duplicados que salen del solape los quita select_moments."""
    overlap = max(0, min(config.ANALYSIS_OVERLAP, WINDOW // 3))
    out, i, n = [], 0, len(segments)
    while i < n:
        t0 = segments[i]["start"]
        j = i
        while j < n and (segments[j]["start"] - t0 <= WINDOW or j == i):
            j += 1
        out.append(segments[i:j])
        if j >= n:
            break
        # la siguiente ventana arranca `overlap` segundos antes del final de esta (pero siempre avanza)
        cut = segments[j - 1]["end"] - overlap
        k = j - 1
        while k > i and segments[k - 1]["end"] > cut:
            k -= 1
        i = max(k, i + 1)
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


def _parse_scores(txt):
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b < 0:
        return None
    try:
        data = json.loads(txt[a : b + 1])
    except json.JSONDecodeError:
        return None
    sc = data.get("scores") if isinstance(data, dict) else None
    return sc if isinstance(sc, list) else None


def _line(s):
    spk = f" {s['spk']}:" if s.get("spk") else ""
    note = f" ({s['note']})" if s.get("note") else ""
    return f"[{int(s['start'])}]{(' ' + s['hot']) if s.get('hot') else ''}{spk} {s['text']}{note}"


def _build_prompt(chunk, want, secs, prof=None, game=None):
    prof = prof or profiles.get("auto")
    game_line = f"El juego es: {str(game).strip()[:60]}. Usa su vocabulario para entender las jugadas." if game and str(game).strip() else ""
    text = "\n".join(_line(s) for s in chunk)
    return PROMPT.format(want=want, secs=secs, lo=int(secs * 0.75), hi=int(secs * 1.3), text=text,
                         kind=prof["kind"], guide=prof["guide"], game_line=game_line)


def _ask_llm(chunk, want, secs, prof=None, game=None):
    """Pregunta a la IA. Si un proveedor se queda sin cupo, llm.py pasa solo al siguiente."""
    return llm.ask(_build_prompt(chunk, want, secs, prof, game), check=_parse_moments)


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


def _tags(raw):
    """Hashtags limpios: '#palabra', sin repetir, máx. 8."""
    out = []
    items = raw if isinstance(raw, list) else re.split(r"[\s,]+", str(raw or ""))
    for t in items:
        t = re.sub(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ_]", "", str(t))
        if t and ("#" + t.lower()) not in [x.lower() for x in out]:
            out.append("#" + t)
        if len(out) >= 8:
            break
    return out


def _clean(m, secs, duration):
    try:
        start, end = float(m["start"]), float(m["end"])
        score = int(max(0, min(100, float(m.get("score", 50)))))
    except (KeyError, TypeError, ValueError):
        return None
    if end <= start:
        end = start + secs
    length = min(max(end - start, secs * 0.6), secs * 1.4)
    end = min(start + length, duration)
    if end - start < 5:
        return None
    return {"start": start, "end": end, "score": score,
            "title": str(m.get("title", "Clip"))[:80], "reason": str(m.get("reason", "")),
            "hook": str(m.get("hook", "") or "").strip()[:70],
            "description": str(m.get("description", "") or "").strip()[:300],
            "hashtags": _tags(m.get("hashtags"))}


# ----------------------------------------------------------------------------- pistas
def _text_of(m, segments, limit=None):
    txt = " ".join(s["text"] for s in segments
                   if s["end"] > m["start"] and s["start"] < m["end"] and s.get("text") != ACTION_TEXT)
    return txt[:limit] if limit else txt


def keyword_hits(m, segments, prof):
    words = prof.get("keywords") or []
    if not words:
        return []
    txt = profiles.norm(_text_of(m, segments))
    return [k for k in words if profiles.norm(k) in txt]


def _boost(cands, segments, prof=None, bonus=None):
    """Sube el puntaje (máx. 100) de los momentos con picos de volumen, acción en pantalla, chat o palabras clave."""
    prof = prof or profiles.get("auto")
    per = dict(prof["bonus"])
    if bonus is not None:                    # compatibilidad: un bonus fijo para cualquier pista
        per = {k: bonus for k in per}
    hot = [s for s in segments if s.get("hot")]
    for m in cands:
        add, tags = 0, set()
        inside = [s for s in hot if s["end"] > m["start"] and s["start"] < m["end"]]
        for s in inside:
            tags.update(c for c in s["hot"])
        for mark, key in profiles.MARKS:
            if mark in tags:
                add += per.get(key, 0)
        hits = keyword_hits(m, segments, prof)
        if hits:
            add += profiles.KEYWORD_BONUS
        if add:
            m["score"] = min(100, m["score"] + min(add, 14))
            extra = "".join(sorted(tags)) + (" 🔑" if hits else "")
            m["reason"] = (m["reason"] + " " + extra).strip()


def _snap_all(cands, words, segments, secs, duration, prof):
    if not words or not config.SNAP_CUTS:
        return cands
    out = []
    for m in cands:
        n = snap.snap_moment(m, words, segments, secs, prof, duration)
        out.append(n)
    return out


def rerank(cands, segments, n_clips, prof=None, max_items=60):
    """Segunda pasada: la IA ve todos los candidatos juntos y los re-puntúa (mezcla 40% original, 60% nueva).
    Si algo falla (sin cupo, respuesta rara) deja los puntajes como estaban."""
    if not config.RERANK or len(cands) <= n_clips or len(cands) < 3:
        return cands
    prof = prof or profiles.get("auto")
    top = sorted(cands, key=lambda m: m["score"], reverse=True)[:max_items]
    items = "\n".join(f"#{i} [{int(m['start'])}-{int(m['end'])}s] ({m['title']}) {_text_of(m, segments, 320)}"
                      for i, m in enumerate(top))
    prompt = RERANK_PROMPT.format(n=len(top), guide=prof["guide"], items=items)
    try:
        scores = llm.ask(prompt, check=_parse_scores)
    except Exception as e:  # noqa: BLE001  (la segunda pasada es un extra: nunca debe tumbar el trabajo)
        print(f"  Segunda pasada: no pude ({type(e).__name__}); dejo los puntajes como estaban.", flush=True)
        return cands
    n = 0
    for it in scores:
        try:
            i, sc = int(it["i"]), float(it["score"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= i < len(top):
            top[i]["score"] = int(max(0, min(100, round(0.4 * top[i]["score"] + 0.6 * sc))))
            n += 1
    print(f"  Segunda pasada: re-puntué {n} de {len(top)} candidatos", flush=True)
    return cands


# ----------------------------------------------------------------------------- API pública
def find_moments(segments, n_clips, secs, words=None, profile=None, game=None, video=None, known_texts=None):
    """video = ruta del video (para verificar con imágenes); known_texts = textos de clips ya hechos (para no repetir otra cámara)."""
    prof = profiles.get(profile) if not isinstance(profile, dict) else profile
    duration = segments[-1]["end"] if segments else 0
    chunks = _chunks(segments)
    want = min(40, max(3, math.ceil(n_clips * 2.0 / max(1, len(chunks)))))   # pide de más: luego se quitan solapes y se queda con los mejores
    cands = []
    for ch in chunks:
        for m in _ask_llm(ch, want, secs, prof, game):
            c = _clean(m, secs, duration)
            if c:
                cands.append(c)
    cands = _snap_all(cands, words, segments, secs, duration, prof)
    _boost(cands, segments, prof)
    rerank(cands, segments, n_clips, prof)
    if video is not None:
        vision.verify(cands, video, prof, lambda m, lim=None: _text_of(m, segments, lim))
    dropped = []
    if prof.get("dedupe") and config.DEDUPE:
        ranked = sorted(cands, key=lambda m: m["score"], reverse=True)
        cands, dropped = detect.drop_repeats(ranked, lambda m: _text_of(m, segments), known_texts or [], config.DEDUPE_THRESHOLD)
        if dropped:
            print(f"  Repetidos: quité {len(dropped)} candidato(s) que cuentan lo mismo que otro clip", flush=True)
    chosen, rejected = select_moments(cands, n_clips)
    return chosen, rejected + dropped


def review_window(segments, secs, existing, duration, min_score=None, max_new=None, words=None, profile=None, game=None, known_texts=None):
    """Revisión en vivo: mira la ventana reciente y devuelve (nuevos_clips, descartados).

    existing = clips ya creados (para no repetir el mismo momento).
    duration = hasta dónde hay transcripción (ningún clip puede pasarse de ahí).
    """
    prof = profiles.get(profile) if not isinstance(profile, dict) else profile
    min_score = config.LIVE_MIN_SCORE if min_score is None else min_score
    max_new = config.LIVE_MAX_NEW if max_new is None else max_new
    cands = []
    for ch in _chunks(segments):
        for m in _ask_llm(ch, 4, secs, prof, game):
            c = _clean(m, secs, duration)
            if c:
                cands.append(c)
    cands = _snap_all(cands, words, segments, secs, duration, prof)
    _boost(cands, segments, prof)
    ranked = sorted(cands, key=lambda x: x["score"], reverse=True)
    chosen, rejected = [], []
    if prof.get("dedupe") and config.DEDUPE and known_texts:
        ranked, dup = detect.drop_repeats(ranked, lambda m: _text_of(m, segments), known_texts, config.DEDUPE_THRESHOLD)
        rejected.extend(dup)
    for m in ranked:
        if any(_overlap(m, c) > 0.3 for c in existing + chosen):
            rejected.append({"title": m["title"], "score": m["score"], "reason": "Ese momento o tema ya tiene clip"})
        elif m["score"] < min_score:
            rejected.append({"title": m["title"], "score": m["score"], "reason": f"Puntaje bajo (mínimo {min_score})"})
        elif len(chosen) >= max_new:
            rejected.append({"title": m["title"], "score": m["score"], "reason": f"Ya se eligieron {max_new} mejores en esta revisión"})
        else:
            chosen.append(m)
    return chosen, rejected


TITLE_PROMPT = """Eres editor de clips virales. Dame título y gancho para este clip (transcripción abajo).
Responde SOLO JSON: {{"title":"título corto y llamativo (máx 70 car.)","hook":"frase gancho de 3 a 7 palabras","description":"1 o 2 frases para redes","hashtags":["#a","#b","#c","#d","#e"]}}
TRANSCRIPCIÓN:
{text}
"""


def title_for(text, fallback="Clip manual"):
    """Título/gancho/descripción para un clip pedido a mano ('Clip ahora'). Si la IA falla, usa textos simples."""
    base = {"title": fallback, "hook": "¡MIRA ESTO!", "description": "", "hashtags": []}
    text = (text or "").strip()
    if len(text) < 20:
        return base

    def chk(t):
        a, b = t.find("{"), t.rfind("}")
        try:
            d = json.loads(t[a : b + 1]) if a >= 0 and b > a else None
        except json.JSONDecodeError:
            return None
        return d if isinstance(d, dict) and d.get("title") else None

    try:
        d = llm.ask(TITLE_PROMPT.format(text=text[:3000]), check=chk)
    except Exception:  # noqa: BLE001
        return base
    return {"title": str(d.get("title", fallback))[:80], "hook": str(d.get("hook", "") or base["hook"])[:70],
            "description": str(d.get("description", "") or "")[:300], "hashtags": _tags(d.get("hashtags"))}
