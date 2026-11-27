"""Buscador de clips virales en TikTok / Instagram Reels.

El buscador NO descarga videos: lee metadatos públicos con yt-dlp (perfiles y links), descarta lo viejo,
lo poco visto y lo que tiene marca ajena, y encola los mejores como si los hubieras pegado en «Crear clips».
De ahí siguen por el pipeline normal: web (Storage + tabla clips) y Facebook (cola automática).

Backends (en orden de fiabilidad):
  • links directos de video/reel  -> yt-dlp, funciona sin cookies en TikTok
  • perfiles de TikTok           -> tiktok:user con yt-dlp (funciona leyendo metadatos planos)
  • hashtags de Instagram        -> instagram:tag con yt-dlp (necesita COOKIES_FILE; si falla, se omite)

No hay llaves en este archivo: credenciales y cookies salen de worker/.env (config).
"""
import math
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

import config
import db

SPONSOR = ("patrocinad", "publicidad", "promocion", "promo ", "advertisement", "sponsored", "©", "marca registrada")

PROMPT_MARCA = """Mira esta miniatura de un video que queremos recomendar. ¿Tiene marca, logo, watermark o texto de otro creador o empresa (no de TikTok/Instagram ni del propio video)?
Responde SOLO JSON: {"branded": true|false, "what": "qué marca o logo se ve, o nada"}
Reglas: un nombre de usuario pequeño o el icono de la red NO cuenta como marca; un logo comercial, una marca de ropa, un canal ajeno o texto publicitario SÍ cuenta."""


# --------------------------------------------------------------------------- helpers puros
def network_of(url):
    host = (urlparse(str(url)).netloc or "").lower()
    if "tiktok.com" in host or host.startswith("vm.tiktok.com") or host.startswith("vt.tiktok.com"):
        return "tiktok"
    if "instagram.com" in host or host.startswith("reel.link"):
        return "instagram"
    return ""


def parse_targets(text):
    """Texto libre -> links de perfiles/videos. Acepta @usuario, tiktok.com/@... y #hashtag."""
    out, seen = [], set()
    for t in re.split(r"[\s,;]+", str(text or "").strip()):
        t = t.strip().strip("'\"")
        if not t:
            continue
        if not t.startswith("http") and "#" in t:
            t = "https://www.instagram.com/explore/tags/" + t.lstrip("#@") + "/"
        elif t.startswith("@") or re.match(r"^(www\.)?(tiktok|instagram)\.com/", t, re.I):
            net = "instagram" if "instagram" in t else "tiktok"
            if t.startswith("@"):
                t = ("https://www.instagram.com/" if net == "instagram" else "https://www.tiktok.com/@") + t.lstrip("@")
            elif not t.startswith("http"):
                t = "https://" + t
        elif not t.startswith("http"):
            t = "https://www.tiktok.com/@" + t.lstrip("@/")
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def is_video_url(url):
    """Solo links a un video/reel concreto; un perfil se trata como fuente de muchos videos."""
    p = urlparse(str(url))
    parts = [x for x in p.path.split("/") if x]
    if not parts:
        return False
    if network_of(url) == "tiktok":
        return any(p in ("video", "photo") for p in parts[:-1]) and len(parts) > 1
    if network_of(url) == "instagram":
        return any(p in ("reel", "reels", "p", "tv") for p in parts[:-1]) and len(parts) > 1
    return False


def evaluate(info, opts, now=None):
    """(sirve, motivo, puntaje, velocidad). `info` = entry plana de yt-dlp."""
    now = now or datetime.now(timezone.utc)
    views = int(info.get("view_count") or info.get("views") or 0)
    if views < int(opts.get("min_views") or config.SEARCH_MIN_VIEWS):
        return False, f"pocas vistas ({views:,})", 0, 0.0
    dur = float(info.get("duration") or 0)
    if dur and (dur < 3 or dur > 600):
        return False, "duración fuera de rango", 0, 0.0
    if str(info.get("live_status") or "") in ("is_live", "is_upcoming"):
        return False, "es un directo", 0, 0.0
    ts = info.get("timestamp")
    try:
        age_h = max(0.0, (now - datetime.fromtimestamp(float(ts), timezone.utc)).total_seconds() / 3600) if ts else 24.0
    except (ValueError, OverflowError, OSError):
        age_h = 24.0
    if age_h > int(opts.get("max_age_hours") or config.SEARCH_MAX_AGE_HOURS):
        return False, "ya es viejo", 0, 0.0
    speed = views / max(age_h, 1.0)
    likes = int(info.get("like_count") or info.get("likes") or 0)
    comments = int(info.get("comment_count") or info.get("comments") or 0)
    eng = 100.0 * likes / max(views, 1)
    if eng < config.SEARCH_MIN_ENGAGEMENT:
        return False, f"poca interacción ({eng:.1f}%)", 0, round(speed, 1)
    score = (min(35.0, 5.0 * math.log10(max(views, 10)))
             + min(25.0, 8.0 * math.log10(max(speed, 1)))
             + min(20.0, eng * 2.0)
             + max(0.0, 15.0 - age_h / 6.0)
             + min(10.0, comments / max(views, 1) * 300.0))
    return True, "", int(round(min(100, score))), round(speed, 1)


def branded_by_text(title):
    low = str(title or "").lower()
    return any(w in low for w in SPONSOR)


# --------------------------------------------------------------------------- yt-dlp
def _opts(flat=True):
    o = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20,
         "ignoreerrors": True, "retries": 1}
    if config.COOKIES_FILE:
        o["cookiefile"] = config.COOKIES_FILE
    if flat:
        o["extract_flat"] = "in_playlist"
    return o


def _extract(url, flat=True, playlistend=20):
    import yt_dlp
    o = _opts(flat)
    if flat:
        o["playlistend"] = playlistend
    with yt_dlp.YoutubeDL(o) as y:
        return y.extract_info(url, download=False)


def _normalize(entry, net, source_url):
    e = entry or {}
    vid = str(e.get("id") or "")
    url = e.get("webpage_url") or e.get("url") or source_url
    if url and not str(url).startswith("http"):
        net = net or network_of(source_url)
        url = (f"https://www.tiktok.com/@user/video/{vid}" if net == "tiktok"
               else f"https://www.instagram.com/reel/{vid}/")
    return {"network": net or network_of(url), "video_id": vid, "url": url,
            "title": (e.get("title") or e.get("description") or "")[:300],
            "views": int(e.get("view_count") or 0), "likes": int(e.get("like_count") or 0),
            "comments": int(e.get("comment_count") or 0), "duration": int(e.get("duration") or 0),
            "timestamp": e.get("timestamp"), "thumbnail": e.get("thumbnail")}


def collect(accounts, links, limit, log=print):
    """Lista de candidatos únicos. `accounts`/`links` = listas de URLs."""
    out, seen = [], set()
    targets = list(dict.fromkeys(list(links or []) + list(accounts or [])))[: max(1, config.SEARCH_ACCOUNTS) + 20]
    for url in targets:
        net = network_of(url)
        if not net:
            continue
        try:
            if is_video_url(url):
                info = _extract(url, flat=False)
                cands = [_normalize(info, net, url)] if info and info.get("id") else []
            else:
                info = _extract(url, flat=True, playlistend=max(limit * 2, 20))
                cands = [_normalize(e, net, url) for e in ((info or {}).get("entries") or [])]
        except Exception as e:  # noqa: BLE001  (un perfil privado o bloqueado no tumba la búsqueda)
            log(f"  Buscador: no pude leer {url[:80]} ({type(e).__name__})")
            continue
        for c in cands:
            if not c["video_id"] or not c["url"] or c["video_id"] in seen:
                continue
            seen.add(c["video_id"])
            out.append(c)
        if len(out) >= limit * 4:
            break
    return out


def check_brand(c, log=print):
    """(sirve, motivo). Filtro de marca ajena: texto sospechoso + visión sobre la miniatura."""
    if branded_by_text(c.get("title")):
        return False, "texto publicitario en el título"
    if not config.SEARCH_BRAND_FILTER:
        return True, ""
    try:
        import llm
        if not llm.vision_available():
            return True, ""
        info = _extract(c["url"], flat=False)
        thumb = (info or {}).get("thumbnail")
        if not thumb:
            return True, ""
        r = requests.get(thumb, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if not r.ok or len(r.content) > 2_000_000:
            return True, ""
        def parse(txt):
            import json
            m = re.search(r"\{.*\}", txt, re.S)
            if not m:
                return None
            d = json.loads(m.group(0))
            return d if isinstance(d, dict) and isinstance(d.get("branded"), bool) else None
        d = llm.ask_vision(PROMPT_MARCA, [r.content], check=parse)
        if d and d.get("branded"):
            return False, f"marca ajena: {str(d.get('what') or 'logo')[:80]}"
    except Exception as e:  # noqa: BLE001  (es un extra: sin IA de visión, se acepta el clip)
        log(f"  Buscador: no pude revisar la marca ({type(e).__name__})")
    return True, ""


# --------------------------------------------------------------------------- trabajo del worker
def process(job):
    """Corre un trabajo 'search'. `payload` trae search_id y las opciones de la búsqueda."""
    p = job.get("payload") or {}
    sid = p.get("search_id")
    if not sid:
        raise RuntimeError("el trabajo de búsqueda no trae search_id")
    try:
        _run(job, p, sid)
    except Exception as e:  # noqa: BLE001
        db.update_search(sid, status="error", error=str(e)[:400], finished_at=db.now())
        raise


def _run(job, p, sid):
    search = db.get_search(sid) or {}
    opts = {**search, **p}

    if p.get("mode") == "queue":     # botón «Encolar» de la web
        ids = list(p.get("ids") or [])
        n = 0
        for rid in ids:
            row = db.get_search_result(rid)
            if not row or row.get("status") == "queued" or not row.get("url"):
                continue
            db.create_search_source(row, opts, sid, rid)
            n += 1
        db.update_search(sid, queued=int(search.get("queued") or 0) + n)
        print(f"Buscador: encolé {n} video(s) a mano.", flush=True)
        return

    db.update_search(sid, status="running", error=None, finished_at=None)
    accounts = [u for u in (opts.get("accounts") or []) if u]
    links = [u for u in (opts.get("links") or []) if u]
    if not accounts and not links:
        accounts = list(config.SEARCH_SEEDS)
    if not accounts and not links:
        raise RuntimeError("escribe al menos un perfil de TikTok/Reels o pega links de videos")

    limit = max(1, min(50, int(opts.get("max_results") or 10)))
    auto_queue = max(0, min(30, int(opts.get("auto_queue") if opts.get("auto_queue") is not None else 5)))
    print(f"Buscador: revisando {len(accounts)} perfil(es) y {len(links)} link(s) · hasta {limit} resultados", flush=True)

    cands = collect(accounts, links, limit)
    nets = [str(n).strip().lower() for n in (opts.get("networks") or []) if n]
    if nets:
        cands = [c for c in cands if c.get("network") in nets]
    already = db.search_known_urls([c["url"] for c in cands])
    rows, accepted, queued = [], [], 0
    for c in cands:
        ok, reason, score, speed = evaluate(c, opts)
        if not ok:
            rows.append({**c, "score": score, "velocity": speed, "status": "skipped", "reason": reason, "posted_at": _posted(c)})
            continue
        if c["url"] in already or branded_by_text(c.get("title")):
            rows.append({**c, "score": score, "velocity": speed, "status": "skipped", "reason": "ya está en la web o es publicidad", "posted_at": _posted(c)})
            continue
        accepted.append({**c, "score": score, "velocity": speed, "posted_at": _posted(c)})

    accepted.sort(key=lambda x: (-x["score"], -x["velocity"]))
    for c in accepted[: min(len(accepted), max(config.SEARCH_INSPECT, 0))]:
        ok, reason = check_brand(c)
        c["status"] = "found" if ok else "rejected"
        c["reason"] = "" if ok else reason
    for c in accepted:
        c.setdefault("status", "found")
        c.setdefault("reason", "")
        if c["status"] == "found" and queued < auto_queue:
            try:
                sid_src = db.create_search_source(c, opts, sid)
                c["status"], c["source_id"] = "queued", sid_src
                queued += 1
            except Exception as e:  # noqa: BLE001
                c["status"], c["reason"] = "skipped", f"no pude encolarlo ({type(e).__name__})"

    cols = {"search_id", "network", "video_id", "url", "title", "views", "likes", "comments",
            "duration", "posted_at", "score", "velocity", "status", "reason", "source_id"}
    clean = [{k: c.get(k) for k in cols} | {"search_id": sid}
             for c in (rows + accepted)[: limit * 3]]
    if clean:
        db.save_search_results(clean)
    db.update_search(sid, status="done", found=len(clean), queued=queued, finished_at=db.now())
    print(f"Buscador: {len(cands)}video(s) vistos · {len(clean)} guardados · {queued} encolados", flush=True)


def _posted(c):
    try:
        return datetime.fromtimestamp(float(c["timestamp"]), timezone.utc).isoformat() if c.get("timestamp") else None
    except (ValueError, OverflowError, OSError, TypeError):
        return None
