"""Programación: publica en tu página de Facebook los clips cuya hora ya llegó (solo si FB_PAGE_ID y FB_PAGE_TOKEN están en .env).

La web guarda scheduled_at + publish_status='scheduled'. Aquí se revisa cada SCHEDULE_CHECK_SECONDS cuando el worker está libre.
Un clip que falla pasa a 'error' (con el motivo) y NO se reintenta solo: así nunca publica dos veces.
"""
import time
from datetime import datetime, timezone
from pathlib import Path

import config
import packager

_last = 0.0


def is_due(row, now=None):
    """Lógica pura: ¿ya llegó la hora de este clip?"""
    if (row or {}).get("publish_status") != "scheduled" or not row.get("scheduled_at"):
        return False
    now = now or datetime.now(timezone.utc)
    try:
        when = datetime.fromisoformat(str(row["scheduled_at"]).replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when <= now


def publish_one(row, db, publisher, workdir):
    """Baja el clip, lo publica y anota el resultado. Devuelve True si salió."""
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    f = workdir / f"sched_{row['id']}.mp4"
    try:
        if not row.get("storage_path"):
            raise RuntimeError("el clip no tiene archivo")
        f.write_bytes(db.download_clip(row["storage_path"]))
        # se marca ANTES de publicar: si el worker se cae a mitad, no se publica dos veces
        db.update_clip(row["id"], publish_status="error", publish_error="interrumpido mientras publicaba; revisa tu página")
        vid = publisher.publish_reel(f, packager.caption_for(row, "reels"))
        if not vid:
            raise RuntimeError("Facebook no aceptó el Reel (mira la consola del worker)")
        db.update_clip(row["id"], publish_status="published", publish_error=None, fb_video_id=str(vid),
                       published_at=datetime.now(timezone.utc).isoformat())
        return True
    except Exception as e:  # noqa: BLE001
        db.update_clip(row["id"], publish_status="error", publish_error=str(e)[:200])
        print(f"  Programación: no pude publicar {row.get('id')} ({type(e).__name__}: {str(e)[:120]})", flush=True)
        return False
    finally:
        f.unlink(missing_ok=True)


def tick(db=None, publisher=None):
    """Llamar desde el bucle del worker cuando está libre. No hace nada sin credenciales de Facebook."""
    global _last
    if not (config.FB_PAGE_ID and config.FB_PAGE_TOKEN):
        return 0
    if time.time() - _last < config.SCHEDULE_CHECK_SECONDS:
        return 0
    _last = time.time()
    if db is None:
        import db as db
    if publisher is None:
        import publisher
    done = 0
    for row in db.due_clips():
        if is_due(row) and publish_one(row, db, publisher, config.WORK_DIR / "sched"):
            done += 1
            print(f"  Programación: publicado «{row.get('title')}»", flush=True)
    return done
