"""Canales automáticos: cada WATCH_SECONDS mira si alguno de tus canales entró en vivo y, si es así, crea solo el
trabajo de grabación (igual que si pegaras el link en En vivo). Solo corre cuando el worker está libre."""
import time

import config
import db

_last = 0.0
_warned = False


def live_url_for(url: str) -> str:
    """Un canal de YouTube (@nombre, /channel/, /c/, /user/) se mira por su pestaña /live. Lo demás se deja igual."""
    u = (url or "").strip().rstrip("/")
    low = u.lower()
    if ("youtube.com" in low or "youtu.be" in low) and not any(k in low for k in ("watch?", "/live", "youtu.be/")):
        return u + "/live"
    return u


def probe(url: str):
    """Devuelve {id, url, title} si el canal está en vivo ahora mismo; None si no lo está (o no se pudo saber)."""
    import yt_dlp

    opts = {"quiet": True, "noplaylist": True, "skip_download": True, "socket_timeout": 20,
            "remote_components": ["ejs:github"]}
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(live_url_for(url), download=False)
    except Exception:  # noqa: BLE001  (no está en vivo, canal inexistente o YouTube no respondió: se mira otra vez luego)
        return None
    if not info or not info.get("is_live"):
        return None
    vid = info.get("id") or info.get("webpage_url") or url
    return {"id": str(vid), "url": info.get("webpage_url") or url, "title": info.get("title") or url}


def tick(force=False) -> int:
    """Revisa los canales activos. Devuelve cuántos directos nuevos puso en cola."""
    global _last, _warned
    if not force and time.time() - _last < config.WATCH_SECONDS:
        return 0
    _last = time.time()
    try:
        channels = db.active_channels()
    except Exception as e:  # noqa: BLE001
        if not _warned:
            print(f"Canales automáticos: no pude leer la tabla watch_channels ({str(e)[:80]}). Corre 0006_envivo.sql.", flush=True)
            _warned = True
        return 0
    if not channels or db.live_active():
        return 0
    started = 0
    for ch in channels:
        found = probe(ch["url"])
        db.update_channel(ch["id"], last_checked=db.now(), last_status="en vivo" if found else "sin directo")
        if not found or found["id"] == ch.get("last_video_id"):
            continue      # no está en vivo, o es el mismo directo que ya se grabó / que paraste a mano
        sid = db.create_live_source(ch, found)
        db.update_channel(ch["id"], last_video_id=found["id"], last_status="grabando")
        print(f"Canal '{ch.get('name') or ch['url']}' entró en vivo → grabo: {found['title']}", flush=True)
        started += 1
        break             # el worker graba un directo a la vez
    return started
