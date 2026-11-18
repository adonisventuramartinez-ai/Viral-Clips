"""Gancho: que el clip ARRANQUE en lo mejor y que el texto de arriba enganche. Lógica pura, con pruebas (test_gancho.py).

  refine_start(words, start, end)  -> (nuevo_inicio, nota)   mueve el inicio a la primera frase fuerte (máx. unos segundos)
  best_hook(ai_hook, title, words, start, end) -> texto corto para poner arriba del clip

Por qué: en los primeros 2-3 segundos la gente decide si se queda. Un corte que empieza en "bueno, eh, entonces..." o en
una frase que depende de la anterior ("pero eso no es lo peor") pierde a quien mira. Esto NO cambia lo que se dice: solo
elige dónde entra el clip y qué texto lo anuncia. Si no está seguro, no toca nada.
"""
import re
import unicodedata

import viral

# Muletillas y saludos: nunca deberían ser lo primero que se oye.
FILLER_OPEN = {"bueno", "eh", "ehh", "este", "mmm", "mm", "ok", "okay", "pues", "hola", "buenas", "bienvenidos",
               "saludos", "dale", "ya", "listo", "aja", "ajá", "a ver", "vamos", "entonces", "claro", "mira",
               "oye", "oigan", "amigos", "gente", "hermano", "mano", "klk", "qué lo qué", "klk", "vaina",
               "tiguere", "chercha", "jevi", "pariguayo", "dime a ver", "manin", "colmadito", "jevi", "pariguayo",
               "oye", "mira", "escucha", "atiende", "fijate", "imaginate", "sabes", "sabes que", "sabes qué",
               "la verdad", "la neta", "en serio", "en verdad", "de verdad", "de veras", "en realidad",
               "pues", "entonces", "asi que", "así que", "por eso", "por lo tanto", "de hecho", "de hecho que"}
# Palabras que enganchan con lo que se dijo ANTES (el clip no se entiende empezando ahí).
DEPENDENT_OPEN = {"y", "pero", "porque", "entonces", "sino", "tambien", "ademas", "luego", "eso", "esa", "ese", "asi",
                  "o", "ni", "aunque", "mientras", "que", "como", "cuando", "donde", "quien", "cual",
                  "cuyo", "cuya", "cuyos", "cuyas", "cuyo", "cuya", "cuyos", "cuyas", "cuyo", "cuya"}
# Ganchos genéricos que no dicen nada: se cambian por algo del propio clip.
GENERIC = {"mira esto", "mira", "mira lo que paso", "nadie lo esperaba", "momento clave", "no lo vas a creer", "increible",
           "wow", "mira lo que hizo", "esto es una locura", "no lo vas a creer", "tienes que ver esto", "momento viral",
           "no te lo pierdas", "esto es increible", "mira esto que paso", "no vas a creer", "esto es brutal",
           "klk", "vaina", "tremendo", "brutal", "loco", "insano", "salvaje", "fuerte", "duro",
           "esto es tremendo", "esto es brutal", "esto es una locura", "no te lo pierdas", "mira esto que paso"}
TAIL_STOP = {"de", "la", "el", "los", "las", "un", "una", "que", "y", "o", "a", "en", "con", "por", "para", "su", "se", "lo", "al", "del",
             "del", "al", "por", "para", "con", "sin", "sobre", "entre", "hasta", "desde", "hacia", "según", "durante"}

SENT_END = re.compile(r"[.?!…]+[\"')\]]*$")
GAP_SENTENCE = 0.6      # una pausa así separa frases aunque Whisper no ponga punto (más sensible)


def norm(text):
    t = unicodedata.normalize("NFD", str(text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9 ]", "", t).strip()


def _in_clip(words, start, end):
    return [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.3]


def sentence_starts(ws):
    """Índices de `ws` donde empieza una frase (por puntuación o por pausa)."""
    out = [0] if ws else []
    for i in range(1, len(ws)):
        prev, cur = ws[i - 1], ws[i]
        if SENT_END.search(str(prev["w"]).strip()) or cur["start"] - prev["end"] >= GAP_SENTENCE:
            out.append(i)
    return out


def start_score(ws, i):
    """0-100: qué tan bien engancha un clip que empiece en la palabra i."""
    text = " ".join(str(x["w"]) for x in ws[i:i + 14])
    s = viral.hook_score(text)
    if "!" in text:
        s += 6
    if "?" in text:
        s += 4
    if any(w in text.lower() for w in ("nadie", "increible", "brutal", "escandalo")):
        s += 8
    first = norm(ws[i]["w"])
    if first in DEPENDENT_OPEN:
        s -= 15
    if first in FILLER_OPEN:
        s -= 15
    if "!" in text:
        s += 4
    t0 = ws[i]["start"]
    if sum(1 for x in ws[i:] if x["start"] - t0 < 3.0) < 4:   # arranque lento: casi nadie habla en los primeros 3 s
        s -= 8
    return s


def _cut_point(ws, i):
    """Segundo exacto donde entrar para empezar en la palabra i sin comerse el final de la anterior."""
    w = ws[i]["start"]
    if i == 0:
        return max(0.0, w - 0.12)
    return max(w - 0.12, (ws[i - 1]["end"] + w) / 2)


def refine_start(words, start, end, max_shift=8.0, min_len=12.0, min_gain=10):
    """Devuelve (inicio, nota). Si hay una frase más fuerte en los primeros `max_shift` s (y el clip sigue durando
    al menos `min_len`), el clip entra ahí. Si no, quita solo muletillas sueltas del arranque. `nota` es None si no cambió nada."""
    ws = _in_clip(words or [], start, end)
    if len(ws) < 8:
        return start, None
    cands = [i for i in sentence_starts(ws) if ws[i]["start"] - start <= max_shift and end - ws[i]["start"] >= min_len]
    if not cands:
        return start, None
    base = start_score(ws, 0)
    best_i, best = 0, base
    for i in cands:
        if i == 0:
            continue
        sc = start_score(ws, i)
        if sc > best:                       # estricto: ante empate se queda lo más temprano
            best_i, best = i, sc
    if best_i and best - base >= min_gain:
        ns = _cut_point(ws, best_i)
        return ns, f"arranque movido +{ns - start:.1f}s ({base}→{best} pts)"
    # no hay una frase mejor: al menos quitar muletillas sueltas al principio ("bueno, eh, ...")
    k = 0
    while k < 2 and k + 5 < len(ws) and norm(ws[k]["w"]) in FILLER_OPEN and ws[k + 1]["start"] - ws[k]["end"] < GAP_SENTENCE \
            and not SENT_END.search(str(ws[k]["w"]).strip()):
        k += 1
    if k and end - ws[k]["start"] >= min_len:
        ns = _cut_point(ws, k)
        return ns, f"quité {k} muletilla(s) del arranque"
    return start, None


# ----------------------------------------------------------------------------- texto del gancho
def clean_hook(h, max_words=9, max_chars=52):
    """Limpia el gancho: sin comillas ni emojis, corto (cabe en 2 líneas arriba del clip) y sin terminar en 'de la…'."""
    h = "".join(ch for ch in str(h or "") if ord(ch) < 0x2190)
    h = re.sub(r"[\"“”«»]", "", h)
    h = " ".join(h.split()).strip(" -–—:;,")
    if not h:
        return ""
    parts = h.split()
    cut = False
    while parts and (len(parts) > max_words or len(" ".join(parts)) > max_chars):
        parts.pop()
        cut = True
    while parts and norm(parts[-1]) in TAIL_STOP:
        parts.pop()
    h = " ".join(parts).rstrip(".,;:")
    return (h + ("…" if cut and not h.endswith(("?", "!")) else "")) if h else ""


def is_generic(h):
    n = norm(h)
    if not n or len(n.split()) < 2:
        return True
    if n in GENERIC:
        return True
    # Detectar ganchos que son solo exclamaciones
    if n in ("wow", "omg", "wtf", "no", "si", "ok", "bueno", "klk", "vaina"):
        return True
    # Detectar ganchos repetitivos (misma palabra 3+ veces)
    words = n.split()
    if len(set(words)) == 1 and len(words) >= 3:
        return True
    # Detectar ganchos muy cortos (menos de 3 palabras)
    if len(words) < 3:
        return True
    # Detectar ganchos que son solo números
    if all(w.isdigit() for w in words):
        return True
    return False


def _sentence_text(ws, a, b):
    return " ".join(str(x["w"]) for x in ws[a:b]).strip().capitalize()


def derive_hook(words, start, end, horizon=16.0):
    """Saca un gancho del propio clip: la frase con más gancho de los primeros `horizon` s. '' si no hay nada decente."""
    ws = _in_clip(words or [], start, min(end, start + horizon))
    if len(ws) < 4:
        return ""
    starts = sentence_starts(ws) + [len(ws)]
    best, best_s = "", -1
    for a, b in zip(starts, starts[1:]):
        txt = _sentence_text(ws, a, b)
        if len(txt.split()) < 3 or viral.risks_in(txt):
            continue
        s = viral.hook_score(txt) + (6 if "!" in txt else 0) - (8 * (norm(ws[a]["w"]) in DEPENDENT_OPEN or norm(ws[a]["w"]) in FILLER_OPEN))
        if s > best_s:
            best, best_s = txt, s
    return clean_hook(best)


def best_hook(ai_hook, title, words, start, end):
    """El gancho que se pone arriba del clip: el de la IA si dice algo; si es genérico, uno sacado del clip; si no, el título."""
    h = clean_hook(ai_hook)
    if h and not is_generic(h) and not viral.risks_in(h):
        return h
    d = derive_hook(words, start, end)
    if d and not is_generic(d):
        return d
    t = clean_hook(title)
    return t or "MIRA ESTO"
