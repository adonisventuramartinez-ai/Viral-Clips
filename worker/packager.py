"""Paquete de publicación de un clip: texto listo para TikTok, Reels/Facebook y Shorts, 3 ganchos alternativos y un comentario fijado.

  build_pack(m, text, cfg)  -> dict (usa la IA; si no responde, usa una plantilla: nunca falla)
  clean_pack(d, ...)        -> límites de cada red (lógica pura, con pruebas)
  caption_for(clip, net)    -> texto final para pegar o publicar
"""
import json
import re

# Límites prácticos de cada red (los reales son más amplios; esto es lo que rinde mejor)
TIKTOK_CAP = 130
REELS_CAP = 220
SHORTS_TITLE = 70
SHORTS_DESC = 300
HOOK_MAX = 60
MAX_TAGS = {"tiktok": 5, "reels": 5, "shorts": 4}

PROMPT = """Eres el community manager de una página de clips de "{show}". Español dominicano natural, sin groserías ni insultos, sin inventar datos.
Del clip saca el paquete de publicación. Devuelve SOLO JSON con esta forma:
{{"tiktok":{{"caption":"máx {tt} car.: el gancho va primero","hashtags":["#a","#b","#c"]}},
"reels":{{"caption":"2 líneas cortas (máx {rl} car.) que terminan con una pregunta para comentar","hashtags":["#a","#b","#c"]}},
"shorts":{{"title":"máx {st} car., con curiosidad, sin spoilear","description":"1 o 2 frases (máx {sd} car.)","hashtags":["#Shorts","#a","#b"]}},
"hooks":["gancho A: curiosidad","gancho B: polémica","gancho C: pregunta"],
"first_comment":"1 pregunta corta para fijar como primer comentario"}}
Los ganchos son de 3 a 7 palabras (máx {hm} car.) y NO repiten el título. Los hashtags son 3 a 5, sin espacios, mezcla de tema y nicho.

Título del clip: {title}
Gancho actual: {hook}
Texto hablado:
{text}"""


def _tags(raw, limit, extra=()):
    """Lista de hashtags limpia: con #, sin espacios ni signos, sin repetir (ignora mayúsculas) y con un tope."""
    out, seen = [], set()
    for t in list(extra) + list(raw or []):
        t = re.sub(r"[^\w#áéíóúüñÁÉÍÓÚÜÑ]", "", str(t).replace(" ", ""))
        t = "#" + t.lstrip("#")
        if len(t) < 3 or len(t) > 30 or t.lower() in seen:
            continue
        seen.add(t.lower())
        out.append(t)
    return out[:limit]


def _cut(text, n):
    """Corta en n caracteres sin partir una palabra y sin dejar signos colgando."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0].rstrip(" ,;:-–")
    return cut + "…"


def fallback_pack(title, description="", hashtags=None, hook=None):
    """Plantilla sin IA: sirve cuando no hay cupo y deja algo usable."""
    title = _cut(title or "Mira esto", SHORTS_TITLE)
    desc = _cut(description or title, SHORTS_DESC)
    tags = hashtags or ["#viral", "#clips"]
    hooks = [h for h in [hook, "MIRA LO QUE PASÓ", "NADIE LO ESPERABA"] if h]
    return clean_pack({
        "tiktok": {"caption": title, "hashtags": tags},
        "reels": {"caption": f"{desc}\n¿Tú qué piensas? Comenta 👇", "hashtags": tags},
        "shorts": {"title": title, "description": desc, "hashtags": tags},
        "hooks": hooks, "first_comment": "¿Tú qué piensas de esto?",
    }, title, tags, source="plantilla")


def _reels_caption(text):
    """Hasta 3 líneas, cada una con su tope; conserva los saltos de línea que puso la IA."""
    lines = [_cut(x, REELS_CAP) for x in str(text or "").replace("\r", "").split("\n") if x.strip()]
    return "\n".join(lines[:3])


def clean_pack(d, title="", base_tags=None, source="ia"):
    """Aplica límites y limpieza a lo que devolvió la IA. Siempre devuelve un paquete completo."""
    d = d if isinstance(d, dict) else {}
    g = lambda k: d.get(k) if isinstance(d.get(k), dict) else {}
    base_tags = base_tags or []
    tt, rl, sh = g("tiktok"), g("reels"), g("shorts")
    hooks, seen = [], set()
    for h in (d.get("hooks") or []):
        h = _cut(str(h).strip().strip("\"'"), HOOK_MAX)
        if h and h.lower() not in seen and h.lower() != str(title).lower():
            seen.add(h.lower())
            hooks.append(h)
    return {
        "tiktok": {"caption": _cut(tt.get("caption") or title, TIKTOK_CAP),
                   "hashtags": _tags(tt.get("hashtags") or base_tags, MAX_TAGS["tiktok"], ["#fyp"])},
        "reels": {"caption": _reels_caption(rl.get("caption") or title),
                  "hashtags": _tags(rl.get("hashtags") or base_tags, MAX_TAGS["reels"])},
        "shorts": {"title": _cut(sh.get("title") or title, SHORTS_TITLE),
                   "description": _cut(sh.get("description") or "", SHORTS_DESC),
                   "hashtags": _tags(sh.get("hashtags") or base_tags, MAX_TAGS["shorts"], ["#Shorts"])},
        "hooks": hooks[:3],
        "first_comment": _cut(d.get("first_comment") or "", 140),
        "source": source,
    }


def _parse(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return d if isinstance(d, dict) and d.get("tiktok") and d.get("shorts") else None


def build_pack(m, text, cfg=None):
    """m = momento del clip (title, hook, description, hashtags). Devuelve el paquete; con IA si hay cupo, con plantilla si no."""
    cfg = cfg or {}
    title = m.get("title") or "Clip"
    try:
        import llm
        d = llm.ask(PROMPT.format(show=cfg.get("show", "tu programa"), tt=TIKTOK_CAP, rl=REELS_CAP, st=SHORTS_TITLE,
                                  sd=SHORTS_DESC, hm=HOOK_MAX, title=title, hook=m.get("hook") or "", text=(text or "")[:2200]),
                    check=_parse)
        pack = clean_pack(d, title, m.get("hashtags"))
        if pack["hooks"]:
            return pack
    except Exception as e:  # noqa: BLE001
        print(f"  Paquete: la IA no respondió ({type(e).__name__}); uso la plantilla.", flush=True)
    return fallback_pack(title, m.get("description", ""), m.get("hashtags"), m.get("hook"))


def caption_for(clip, net="reels"):
    """Texto final para pegar/publicar. clip puede traer 'pack' (nuevo) o solo description/hashtags (clips viejos)."""
    pack = clip.get("pack") if isinstance(clip, dict) else None
    if isinstance(pack, dict) and isinstance(pack.get(net), dict):
        p = pack[net]
        head = p.get("title") if net == "shorts" else p.get("caption")
        body = p.get("description") if net == "shorts" else ""
        return "\n".join(x for x in [head, body, " ".join(p.get("hashtags") or [])] if x).strip()
    desc = (clip.get("description") or clip.get("title") or "").strip()
    tags = " ".join((clip.get("hashtags") or [])[:5])
    return f"{desc}\n{tags}".strip()
