"""Clips automáticos de lo mejor del momento.

Vigila FUENTES que tú eliges (canales de YouTube, una búsqueda, ej. "La Casa de Alofoke 3", una página de Facebook o un canal de Twitch), encuentra videos nuevos que van fuerte
(más vistas por hora desde que se subieron) y crea solo el trabajo de clips. Cada clip pasa por el área viral (Parte 7) y, con
AUTO_QUEUE=1, entra a la cola de publicación (Parte 8).

  evaluate(info, feed, now) -> (sirve, motivo, velocidad)   lógica pura, con pruebas
  pick(items, k)            -> los k más fuertes
  tick(db, lister)          -> una revisión

Facebook (Parte 10) se lista con la Graph API y FB_PAGE_TOKEN: funciona con TUS páginas, y con páginas ajenas solo si tu app de Meta
tiene el permiso "Page Public Content Access". Los videos se descargan después con yt-dlp, como los de YouTube.

"Lo mejor del momento" aquí significa: lo más visto por hora entre lo que ya sigues. No lee tendencias de TikTok ni de otras redes.
"""
import re
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import requests

import config

_last = 0.0


def evaluate(info, feed, now=None):
    """(sirve, motivo, velocidad). info = metadatos de yt-dlp del video."""
    now = now or datetime.now(timezone.utc)
    status = info.get("live_status")
    if info.get("is_live") or status in ("is_live", "is_upcoming"):
        return False, "es un directo en curso o programado", 0.0
    dur = float(info.get("duration") or 0)
    lo, hi = float(feed.get("min_minutes") or 3) * 60, float(feed.get("max_minutes") or 120) * 60
    if dur < lo:
        return False, "muy corto", 0.0
    if dur > hi:
        return False, f"muy largo (más de {int(hi // 60)} min)", 0.0
    ts = info.get("timestamp")
    if not ts:
        return False, "no se sabe cuándo se subió", 0.0
    age_h = (now - datetime.fromtimestamp(float(ts), timezone.utc)).total_seconds() / 3600
    if age_h < 0:
        return False, "fecha rara", 0.0
    if age_h > float(feed.get("max_age_hours") or 48):
        return False, "ya es viejo", 0.0
    views = int(info.get("view_count") or 0)
    if views < int(feed.get("min_views") or 0):
        return False, f"pocas vistas ({views})", 0.0
    return True, "", round(views / max(age_h, 1.0), 1)


def pick(items, k):
    """items = [(velocidad, info)] -> los k de mayor velocidad."""
    return [i for _, i in sorted(items, key=lambda x: -x[0])[: max(0, k)]]


def _opts():
    o = {"quiet": True, "skip_download": True, "socket_timeout": 20, "remote_components": ["ejs:github"]}
    if config.COOKIES_FILE:
        o["cookiefile"] = config.COOKIES_FILE
    return o


# ----------------------------------------------------------------------------- Facebook (Graph API)
FB_API = "https://graph.facebook.com/v21.0"
_FB_FIELDS = "id,title,description,permalink_url,length,created_time,views,live_status,reactions.summary(true).limit(0)"
_FB_BASIC = "id,title,description,permalink_url,length,created_time"


def fb_page_ref(target):
    """Link, nombre o id de una página -> lo que entiende la Graph API (id numérico o nombre de usuario). None si no se entiende."""
    t = (target or "").strip()
    if not t:
        return None
    if re.fullmatch(r"\d{5,}", t):
        return t
    if not re.match(r"https?://", t, re.I):
        t = "https://" + t if re.match(r"(www\.|m\.)?(facebook|fb)\.com", t, re.I) else "https://www.facebook.com/" + t.lstrip("@/")
    u = urlparse(t)
    if "facebook.com" not in (u.netloc or "").lower() and "fb.com" not in (u.netloc or "").lower():
        return None
    q = parse_qs(u.query)
    if q.get("id") and re.fullmatch(r"\d+", q["id"][0]):
        return q["id"][0]
    parts = [p for p in u.path.split("/") if p]
    nums = [p for p in parts if re.fullmatch(r"\d{5,}", p)]
    if parts and parts[0].lower() in ("pages", "people") and nums:
        return nums[-1]
    if parts and parts[0].lower() not in ("watch", "reel", "reels", "videos", "groups", "share", "profile.php", "pg"):
        return parts[0]
    if len(parts) > 1 and parts[0].lower() == "pg":
        return parts[1]
    return None


def _fb_error(r):
    try:
        e = (r.json() or {}).get("error") or {}
    except ValueError:
        e = {}
    code, msg = e.get("code"), (e.get("message") or r.text or "")[:140]
    if code == 190:
        return f"el token de Facebook venció o no sirve (FB_PAGE_TOKEN): {msg}"
    if code in (10, 200, 283) or "permission" in msg.lower():
        return f"Facebook no deja leer esa página con tu token (solo páginas tuyas, o con 'Page Public Content Access'): {msg}"
    return f"Facebook respondió con error: {msg}"


def fb_info(v, now=None):
    """Un video de la Graph API -> el mismo formato que usa evaluate() (lo que da yt-dlp)."""
    ts = None
    ct = v.get("created_time")
    if ct:
        try:
            ts = datetime.fromisoformat(str(ct).replace("Z", "+00:00").replace("+0000", "+00:00")).timestamp()
        except ValueError:
            ts = None
    link = v.get("permalink_url") or ""
    if link.startswith("/"):
        link = "https://www.facebook.com" + link
    views = v.get("views")
    if views is None:     # sin "views": las reacciones sirven de medida aproximada para comparar
        views = (((v.get("reactions") or {}).get("summary")) or {}).get("total_count") or 0
    title = (v.get("title") or "").strip() or " ".join(str(v.get("description") or "").split())[:100] or f"Video de Facebook {v.get('id')}"
    live = str(v.get("live_status") or "").upper()
    return {"id": str(v.get("id")), "title": title, "duration": float(v.get("length") or 0), "timestamp": ts,
            "view_count": int(views or 0), "webpage_url": link or f"https://www.facebook.com/watch/?v={v.get('id')}",
            "live_status": "is_live" if live in ("LIVE", "LIVE_STOPPED_UNPROCESSED") else ("is_upcoming" if live in ("SCHEDULED_UNPUBLISHED", "SCHEDULED_LIVE") else None)}


def fb_list(feed, limit=8, get=None):
    """Lo más reciente de una página de Facebook. Devuelve candidatos con su info ya completa (no hace falta mirar video por video)."""
    get = get or requests.get
    if not config.FB_PAGE_TOKEN:
        raise RuntimeError("falta FB_PAGE_TOKEN en worker/.env para leer Facebook")
    ref = fb_page_ref(feed.get("target"))
    if not ref:
        raise RuntimeError("no entendí el link de la página de Facebook")
    r = get(f"{FB_API}/{ref}/videos", params={"fields": _FB_FIELDS, "limit": limit, "access_token": config.FB_PAGE_TOKEN}, timeout=30)
    if not r.ok:    # algún campo (views, live_status) puede no estar permitido: se reintenta con lo básico
        r2 = get(f"{FB_API}/{ref}/videos", params={"fields": _FB_BASIC, "limit": limit, "access_token": config.FB_PAGE_TOKEN}, timeout=30)
        if not r2.ok:
            raise RuntimeError(_fb_error(r2))
        r = r2
    out = []
    for v in (r.json() or {}).get("data") or []:
        if not v.get("id"):
            continue
        info = fb_info(v)
        out.append({"id": info["id"], "url": info["webpage_url"], "title": info["title"], "info": info})
    return out


def list_candidates(feed, limit=8):
    """Ids y datos básicos de lo más reciente de la fuente (yt-dlp, sin descargar). Devuelve [{id, url, title, view_count, duration}]."""
    if feed.get("kind") == "facebook":
        return fb_list(feed, limit)

    import yt_dlp
    target = (feed.get("target") or "").strip()
    if feed.get("kind") == "twitch":
        base = target.rstrip("/")
        if not base.startswith("http"):
            base = "https://www.twitch.tv/" + base.lstrip("@/")
        urls = [base.rstrip("/") + "/videos?filter=archives&sort=time"]
        fallback_url = lambda vid: f"https://www.twitch.tv/videos/{vid}"
    elif feed.get("kind") == "search":
        urls = [f"ytsearchdate{limit}:{target}"]
        fallback_url = lambda vid: f"https://www.youtube.com/watch?v={vid}"
    else:
        base = target.rstrip("/")
        urls = [base + "/videos", base + "/streams"] if "/watch" not in base and "playlist" not in base else [base]
        fallback_url = lambda vid: f"https://www.youtube.com/watch?v={vid}"

    out, seen = [], set()
    for u in urls:
        try:
            with yt_dlp.YoutubeDL({**_opts(), "extract_flat": "in_playlist", "playlistend": limit}) as y:
                info = y.extract_info(u, download=False)
        except Exception:  # noqa: BLE001  (esa pestaña no existe o la red no respondió)
            continue
        for e in (info or {}).get("entries") or []:
            vid = (e or {}).get("id")
            if vid and vid not in seen:
                seen.add(vid)
                out.append({"id": vid, "url": e.get("url") or fallback_url(vid), "title": e.get("title")})
    return out


def inspect(c):
    """Datos completos de un video (fecha, vistas, duración, si es directo). None si no se pudo."""
    if c.get("info"):       # Facebook: la Graph API ya dio todo
        return c["info"]
    import yt_dlp
    try:
        with yt_dlp.YoutubeDL(_opts()) as y:
            info = y.extract_info(c["url"] if str(c["url"]).startswith("http") else f"https://www.youtube.com/watch?v={c['id']}", download=False)
        return info
    except Exception:  # noqa: BLE001
        return None


def _enabled(db=None):
    """¿Están encendidos los Clips automáticos? Manda el botón de la web (Parte 13); si no se puede leer, el DISCOVER del .env."""
    try:
        if db is None:
            import db as db
        return bool(db.discover_on()) if hasattr(db, "discover_on") else bool(config.DISCOVER)
    except Exception:  # noqa: BLE001
        return bool(config.DISCOVER)


def tick(db=None, lister=None, inspector=None, now=None):
    """Una revisión: mira las fuentes que ya toca revisar y encola los videos más fuertes. Devuelve cuántos encoló."""
    global _last
    if not _enabled(db) or (time.time() - _last < 60 and now is None):
        return 0
    _last = time.time()
    if db is None:
        import db as db
    lister, inspector = lister or list_candidates, inspector or inspect
    queued_total = 0
    try:
        feeds = db.due_feeds(config.DISCOVER_MINUTES)
    except Exception:  # noqa: BLE001
        return 0
    for feed in feeds:
        room = min(config.DISCOVER_MAX_PER_DAY - db.discovered_today(), config.DISCOVER_MAX_QUEUED - db.videos_waiting())
        found, seen_n = [], 0
        try:
            cands = lister(feed)
            known = db.known_video_ids(feed["id"], [c["id"] for c in cands])
            new = [c for c in cands if c["id"] not in known][: config.DISCOVER_INSPECT]
            for c in new:
                info = inspector(c)
                if not info:
                    continue    # no se pudo leer: se vuelve a intentar en la próxima revisión
                seen_n += 1
                ok, why, vel = evaluate(info, feed, now)
                if db.url_already_used(info.get("webpage_url") or c["url"]):
                    ok, why = False, "ya lo tienes en tu biblioteca"
                if ok:
                    found.append((vel, info))
                elif not why.startswith("pocas vistas"):   # "pocas vistas" puede cambiar con las horas: se vuelve a mirar
                    db.remember_video(feed["id"], info, "skipped", why)
            chosen = pick(found, room) if room > 0 else []
            for info in chosen:
                db.create_vod_source(feed, info)
                queued_total += 1
                print(f"Fuente '{feed.get('name') or feed['target']}' → clips de: {info.get('title')}", flush=True)
            # los que sirven pero hoy no hay cupo NO se marcan: se reconsideran en la próxima revisión
            status = f"{len(chosen)} nuevo(s)" if chosen else ("sin cupo hoy" if found and room <= 0 else "nada nuevo")
        except Exception as e:  # noqa: BLE001
            status = f"error: {str(e)[:60]}"
        db.update_feed(feed["id"], last_checked=db.now(), last_status=status)
    return queued_total
