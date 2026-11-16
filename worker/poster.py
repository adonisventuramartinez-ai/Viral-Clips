"""Publica lo que ya llegó a su hora (tabla `posts`) y lo programado a mano en Facebook (scheduler).
Corre en un hilo propio (start_thread) para que un directo largo o un render no frenen las publicaciones.

Seguridad contra publicar dos veces: el post se reserva (queued -> publishing) ANTES de subir; si el worker se cae a mitad queda en
'error: interrumpido' y NO se repite solo. Un error NO se reintenta solo (podría ya haber salido); lo reintentas tú desde la web.
"""
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import config
import packager

NETS = ("facebook", "instagram", "youtube")


def caption(clip, network):
    """(título, texto) de ese clip para esa red."""
    if network == "youtube":
        p = ((clip.get("pack") or {}).get("shorts") or {}) if isinstance(clip.get("pack"), dict) else {}
        title = p.get("title") or clip.get("title") or "Clip"
        body = packager.caption_for(clip, "shorts")
        return title, body
    return clip.get("title") or "", packager.caption_for(clip, "reels")


def publish_post(post, clip, db, workdir=None, fb=None, ig=None, yt=None):
    """Publica un post. Devuelve el id externo o lanza RuntimeError con el motivo."""
    net = post["network"]
    title, text = caption(clip, net)
    if not clip.get("storage_path"):
        raise RuntimeError("el clip no tiene archivo")
    if net == "instagram":
        if ig is None:
            import publisher_ig as ig
        return ig.publish(db.signed_url(clip["storage_path"]), text)
    workdir = Path(workdir or config.WORK_DIR / "posts")
    workdir.mkdir(parents=True, exist_ok=True)
    f = workdir / f"post_{post['id']}.mp4"
    try:
        f.write_bytes(db.download_clip(clip["storage_path"]))
        if net == "facebook":
            if fb is None:
                import publisher as fb
            vid = fb.publish_reel(f, text)
            if not vid:
                raise RuntimeError("Facebook no aceptó el Reel (mira los logs del worker)")
            return vid
        if net == "youtube":
            if yt is None:
                import publisher_yt as yt
            tags = (((clip.get("pack") or {}).get("shorts") or {}).get("hashtags") if isinstance(clip.get("pack"), dict) else None) or clip.get("hashtags")
            return yt.publish(f.read_bytes(), title, text, tags)
        raise RuntimeError(f"red desconocida: {net}")
    finally:
        f.unlink(missing_ok=True)


def tick(db=None, **pubs):
    """Publica los posts vencidos. Devuelve cuántos salieron."""
    if db is None:
        import db as db
    done = 0
    for post in db.due_posts(5):
        if not db.claim_post(post["id"]):
            continue    # otro lo tomó
        clip = db.get_clip(post["clip_id"])
        try:
            if not clip:
                raise RuntimeError("el clip ya no existe")
            ext = publish_post(post, clip, db, **pubs)
            db.update_post(post["id"], status="published", external_id=str(ext), error=None,
                           published_at=datetime.now(timezone.utc).isoformat())
            done += 1
            print(f"  Publicado en {post['network']}: «{(clip or {}).get('title')}»", flush=True)
        except Exception as e:  # noqa: BLE001
            db.update_post(post["id"], status="error", error=str(e)[:300])
            print(f"  No pude publicar en {post['network']} ({type(e).__name__}: {str(e)[:140]})", flush=True)
    return done


def _loop():
    import autoqueue
    import db
    import scheduler
    try:
        db.recover_posts()
    except Exception:  # noqa: BLE001
        pass
    while True:
        for name, fn in (("Programación", scheduler.tick), ("Cola", autoqueue.tick), ("Publicación", tick)):
            try:
                fn()
            except Exception as e:  # noqa: BLE001  (publicar es un extra: nunca debe tumbar nada)
                print(f"{name}: error ({type(e).__name__}: {str(e)[:100]})", flush=True)
        time.sleep(config.POSTER_SECONDS)


def start_thread():
    t = threading.Thread(target=_loop, name="poster", daemon=True)
    t.start()
    return t
