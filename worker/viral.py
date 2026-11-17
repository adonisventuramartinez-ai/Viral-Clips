"""Área "Hacerlo viral": todo clip pasa por aquí ANTES de publicarse.

  run(m, text, cfg, duration)   -> dict `viral` (puntaje, veredicto, mejor título, hashtags, texto de miniatura, riesgos)
  title_score / hashtag_mix / hook_score / combine / verdict   (lógica pura, con pruebas)
  next_slots(now, taken, n)     -> próximas horas buenas para publicar, sin chocar con lo ya programado
  tick()                        -> analiza clips que llegaron sin pasar por aquí (en vivo, rehechos)

Veredicto: "ready" (publicar), "review" (míralo tú), "rejected" (no vale la pena). Riesgos (insultos, acusaciones) siempre van a "review".
La IA es opcional: si no responde se usa el título y hashtags que ya había.
"""
import json
import re
import time
from datetime import datetime, timedelta, timezone

import config

POWER = ("nadie", "increíble", "insólito", "se salió", "explot", "escándalo", "pelea", "descubr", "confes", "reveló", "reaccion",
         "no lo vas", "lo que pasó", "en vivo", "se armó", "tiraera", "verdad", "secreto", "viral", "locura", "tremendo", "épic",
         "brutal", "desastre", "traición", "peleó", "gritó", "lloró", "golpe", "sorprend", "mentira", "bochorno", "caos",
         "tremenda", "brutalidad", "explosión", "escándalo", "polémica", "conflicto", "drama", "tensión", "shock")
RISK_WORDS = ("estafador", "ladrón", "violador", "pedófilo", "asesino", "drogadicto", "corrupto", "puta", "maricón", "hijueputa",
              "maldito", "imbécil", "idiota", "pendejo", "cabrón", "mierda", "coño", "carajo", "jodido", "basura", "escoria")
BROAD_TAGS = ("#fyp", "#viral", "#parati", "#foryou")
_last = 0.0


# ----------------------------------------------------------------------------- lógica pura
def title_score(title):
    """0-100. Premia 25-65 caracteres, palabras de curiosidad/drama, pregunta o número; castiga MAYÚSCULAS completas, signos de más y riesgos."""
    t = " ".join(str(title or "").split())
    if not t:
        return 0
    s = 40
    n = len(t)
    s += 20 if 25 <= n <= 65 else (8 if 15 <= n < 25 or 65 < n <= 80 else -15)
    low = t.lower()
    s += min(24, 8 * sum(1 for w in POWER if w in low))
    if "?" in t or "¿" in t:
        s += 8
    if re.search(r"\d", t):
        s += 5
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7 and n > 12:
        s -= 10
    if re.search(r"[!?]{3,}", t):
        s -= 8
    if any(w in low for w in RISK_WORDS):
        s -= 25
    return max(0, min(100, s))


def risks_in(*texts):
    """Palabras de riesgo (insultos, acusaciones graves) presentes en los textos."""
    low = " ".join(str(t or "") for t in texts).lower()
    return sorted({w for w in RISK_WORDS if w in low})


def hook_score(text):
    """0-100 según qué tan fuerte arranca el clip: mira las primeras ~14 palabras habladas."""
    words = str(text or "").split()[:14]
    if not words:
        return 40
    first = " ".join(words).lower()
    s = 50
    if "?" in first or "¿" in first:
        s += 12
    if any(w in first for w in POWER):
        s += 14
    if re.search(r"\d", first):
        s += 5
    if first.startswith(("bueno", "eh", "este", "mmm", "ok", "okay", "entonces")):
        s -= 12
    if len(words) < 6:
        s -= 8
    return max(0, min(100, s))


def combine(model_score, title_sc, hook_sc, duration):
    """Puntaje final 0-100: 50% lo que vio la IA al elegir el momento, 20% título, 20% arranque, 10% duración ideal (15-60 s)."""
    d = 100 if 15 <= duration <= 60 else (70 if 8 <= duration < 15 or 60 < duration <= 90 else 40)
    return round(0.5 * float(model_score or 0) + 0.2 * title_sc + 0.2 * hook_sc + 0.1 * d)


def verdict(score, risks=()):
    if risks:
        return "review"
    if score >= config.VIRAL_MIN_SCORE:
        return "ready"
    return "review" if score >= config.VIRAL_REVIEW_SCORE else "rejected"


def hashtag_mix(ai_tags, base_tags=(), show="", limit=5):
    """Mezcla ideal: 1 amplio (#fyp), 1-2 del programa/nicho, el resto del tema. Sin repetidos, sin espacios, con #."""
    def clean(t):
        t = "#" + re.sub(r"[^\w]", "", str(t).replace(" ", ""), flags=re.U).lstrip("#")
        return t if 3 <= len(t) <= 30 else None
    out, seen = [], set()

    def add(t):
        t = clean(t) if t else None
        if t and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    add("#fyp")
    if show:
        add(show.replace(" ", ""))
    for t in list(base_tags or []) + list(ai_tags or []):
        if len(out) >= limit:
            break
        if str(t).lower().lstrip("#") in {b.lstrip("#") for b in BROAD_TAGS} and any(o.lower() in BROAD_TAGS for o in out):
            continue   # un solo hashtag amplio
        add(t)
    return out[:limit]


# ----------------------------------------------------------------------------- horas de publicación
def _tz():
    return timezone(timedelta(hours=config.POST_TZ_OFFSET))


def next_slots(now=None, taken=(), n=1, slots=None, tz=None, min_gap_min=None, max_per_day=None):
    """Próximas `n` horas para publicar (UTC). Usa las horas buenas de cada día (POST_SLOTS), salta las que ya están ocupadas
    (a menos de min_gap de otra) y respeta el tope por día. `taken` = fechas ya programadas."""
    tz = tz or _tz()
    slots = slots or config.POST_SLOTS
    gap = timedelta(minutes=config.POST_MIN_GAP_MIN if min_gap_min is None else min_gap_min)
    cap = config.POST_MAX_PER_DAY if max_per_day is None else max_per_day
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    busy = []
    for t in taken:
        try:
            d = t if isinstance(t, datetime) else datetime.fromisoformat(str(t).replace("Z", "+00:00"))
            busy.append((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc))
        except ValueError:
            continue
    hm = []
    for s in slots:
        try:
            h, m = s.split(":")
            hm.append((int(h), int(m)))
        except ValueError:
            continue
    hm.sort()
    if not hm:
        return []
    out, day = [], now.astimezone(tz).date()
    for _ in range(90):
        for h, m in hm:
            cand = datetime(day.year, day.month, day.day, h, m, tzinfo=tz).astimezone(timezone.utc)
            if cand <= now + timedelta(minutes=2):
                continue
            if any(abs(cand - b) < gap for b in busy):
                continue
            if sum(1 for b in busy if b.astimezone(tz).date() == day) >= cap:
                continue
            out.append(cand)
            busy.append(cand)
            if len(out) >= n:
                return out
        day += timedelta(days=1)
    return out


# ----------------------------------------------------------------------------- IA
PROMPT = """Eres experto en contenido viral para Facebook Reels, TikTok y Shorts en español dominicano natural. Sin groserías ni insultos, sin inventar datos. Piensa como un editor que quiere que la gente NO pueda dejar de ver el clip.
Del clip de "{show}" devuelve SOLO JSON:
{{"titles":[{{"t":"título 1 (25-65 car.)","angle":"curiosidad"}},{{"t":"...","angle":"polémica"}},{{"t":"...","angle":"pregunta"}},{{"t":"...","angle":"emoción"}},{{"t":"...","angle":"dato"}}],
"thumb_texts":["2-4 palabras","2-4 palabras","2-4 palabras"],
"hashtags":["#tema1","#tema2","#nicho1","#nicho2","#tema3"],
"risks":["solo si hay insulto, acusación grave contra una persona real o algo que Facebook pueda bloquear; si no, lista vacía"]}}
Reglas de los títulos:
- Generan curiosidad SIN contar el final (nunca reveles el desenlace).
- Empiezan con una promesa o una duda abierta; evita frases vacías ("MIRA ESTO", "INCREÍBLE").
- Usan palabras de drama/emoción cuando el clip las tiene (pelea, secreto, verdad, escándalo, etc.).
- No repiten el título actual; cada uno tiene un ángulo distinto.
- Máximo 65 caracteres; mejor entre 30 y 55.
Los hashtags son 5, sin espacios, mezcla de amplios (#fyp) y del tema/nicho.

Título actual: {title}
Gancho: {hook}
Texto hablado:
{text}"""


def _parse(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return d if isinstance(d, dict) and isinstance(d.get("titles"), list) and d["titles"] else None


def _titles(raw, current):
    """Limpia y puntúa los títulos de la IA (más el actual como opción). Devuelve [{t, angle, score}] de mejor a peor."""
    seen, out = set(), []
    cands = [{"t": current, "angle": "original"}] + [x if isinstance(x, dict) else {"t": str(x)} for x in (raw or [])]
    for x in cands:
        t = " ".join(str(x.get("t", "")).split()).strip("\"' ")[:80]
        if len(t) < 6 or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append({"t": t, "angle": str(x.get("angle") or "")[:20], "score": title_score(t)})
    return sorted(out, key=lambda x: -x["score"])


def run(m, text, cfg=None, duration=None):
    """Analiza un clip. m = momento (title, hook, score, hashtags). Devuelve el dict `viral`; nunca lanza error."""
    cfg = cfg or {}
    show = cfg.get("show") or config.SHOW_NAME
    title0 = m.get("title") or "Clip"
    dur = float(duration if duration is not None else (m.get("end", 0) - m.get("start", 0)) or 30)
    ai = None
    try:
        import llm
        ai = llm.ask(PROMPT.format(show=show, title=title0, hook=m.get("hook") or "", text=(text or "")[:2200]), check=_parse)
    except Exception as e:  # noqa: BLE001
        print(f"  Viral: la IA no respondió ({type(e).__name__}); uso lo que ya había.", flush=True)
    ai = ai if isinstance(ai, dict) else {}
    options = _titles(ai.get("titles"), title0)
    best = options[0]
    texts = [" ".join(str(t).split())[:28] for t in (ai.get("thumb_texts") or []) if str(t).strip()]
    risks = sorted(set(risks_in(best["t"], title0, text)) | {str(r)[:60] for r in (ai.get("risks") or []) if str(r).strip()})
    hsc = hook_score(text)
    score = combine(m.get("score", 70), best["score"], hsc, dur)
    return {
        "version": 1, "score": score, "verdict": verdict(score, risks), "title": best["t"], "title_original": title0,
        "title_score": best["score"], "titles": options[:5], "hook_score": hsc,
        "thumb_text": (texts[0] if texts else " ".join(best["t"].split()[:4])),
        "thumb_texts": texts[:3],
        "hashtags": hashtag_mix(ai.get("hashtags"), m.get("hashtags"), show),
        "risks": risks, "source": "ia" if ai else "reglas", "at": datetime.now(timezone.utc).isoformat(),
    }


def status_for(v):
    """Estado que se guarda en clips.viral_status."""
    return {"ready": "ready", "review": "review", "rejected": "rejected"}.get((v or {}).get("verdict"), "review")


def apply_to_pack(pack, v):
    """Pone los hashtags y el título viral dentro del paquete por red, para que copiar/publicar use lo mejor."""
    if not isinstance(pack, dict) or not v:
        return pack
    tags = v.get("hashtags") or []
    for net, cap in (("tiktok", 5), ("reels", 5), ("shorts", 4)):
        p = pack.get(net)
        if isinstance(p, dict):
            p["hashtags"] = (["#Shorts"] + [t for t in tags if t.lower() != "#shorts"])[:cap] if net == "shorts" else tags[:cap]
    if isinstance(pack.get("shorts"), dict):
        pack["shorts"]["title"] = v["title"][:70]
    return pack


# ----------------------------------------------------------------------------- clips que llegaron sin análisis
def tick(db=None):
    """Cuando el worker está libre: analiza hasta 3 clips pendientes (en vivo, rehechos). Sin miniatura (no baja el video)."""
    global _last
    if not config.VIRAL or time.time() - _last < config.VIRAL_TICK_SECONDS:
        return 0
    _last = time.time()
    if db is None:
        import db as db
    n = 0
    for row in db.clips_needing_viral(3):
        txt = " ".join(str(c.get("w", "")) for c in (row.get("captions") or []) if isinstance(c, dict))
        dur = float(row.get("end_sec") or 0) - float(row.get("start_sec") or 0)
        v = run({"title": row.get("title"), "score": row.get("viral_score"), "hashtags": row.get("hashtags")}, txt, None, dur)
        fields = {"viral": v, "viral_status": status_for(v)}
        if config.VIRAL_AUTO_TITLE and v["title"] != row.get("title"):
            fields["title"] = v["title"]
        db.update_clip(row["id"], **fields)
        n += 1
        print(f"  Viral: «{v['title']}» {v['score']} pts → {v['verdict']}", flush=True)
    return n
