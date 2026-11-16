"""Clips automáticos de lo mejor del momento.

Vigila FUENTES que tú eliges (canales de YouTube o una búsqueda, ej. "La Casa de Alofoke 3"), encuentra videos nuevos que van fuerte
(más vistas por hora desde que se subieron) y crea solo el trabajo de clips. Cada clip pasa por el área viral (Parte 7) y, con
AUTO_QUEUE=1, entra a la cola de publicación (Parte 8).

  evaluate(info, feed, now) -> (sirve, motivo, velocidad)   lógica pura, con pruebas
  pick(items, k)            -> los k más fuertes
  tick(db, lister)          -> una revisión

"Lo mejor del momento" aquí significa: lo más visto por hora entre lo que ya sigues. No lee tendencias de TikTok ni de otras redes.
"""
import time
from datetime import datetime, timezone

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


def list_candidates(feed, limit=8):
    """Ids y datos básicos de lo más reciente de la fuente (yt-dlp, sin descargar). Devuelve [{id, url, title, view_count, duration}]."""
    import yt_dlp
    target = (feed.get("target") or "").strip()
    if feed.get("kind") == "search":
        urls = [f"ytsearchdate{limit}:{target}"]
    else:
        base = target.rstrip("/")
        urls = [base + "/videos", base + "/streams"] if "/watch" not in base and "playlist" not in base else [base]
    out, seen = [], set()
    for u in urls:
        try:
            with yt_dlp.YoutubeDL({**_opts(), "extract_flat": "in_playlist", "playlistend": limit}) as y:
                info = y.extract_info(u, download=False)
        except Exception:  # noqa: BLE001  (esa pestaña no existe o YouTube no respondió)
            continue
        for e in (info or {}).get("entries") or []:
            vid = (e or {}).get("id")
            if vid and vid not in seen:
                seen.add(vid)
                out.append({"id": vid, "url": e.get("url") or f"https://www.youtube.com/watch?v={vid}", "title": e.get("title")})
    return out


def inspect(c):
    """Datos completos de un video (fecha, vistas, duración, si es directo). None si no se pudo."""
    import yt_dlp
    try:
        with yt_dlp.YoutubeDL(_opts()) as y:
            info = y.extract_info(c["url"] if str(c["url"]).startswith("http") else f"https://www.youtube.com/watch?v={c['id']}", download=False)
        return info
    except Exception:  # noqa: BLE001
        return None


def tick(db=None, lister=None, inspector=None, now=None):
    """Una revisión: mira las fuentes que ya toca revisar y encola los videos más fuertes. Devuelve cuántos encoló."""
    global _last
    if not config.DISCOVER or (time.time() - _last < 60 and now is None):
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
