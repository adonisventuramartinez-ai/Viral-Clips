from datetime import datetime, timedelta, timezone

from supabase import create_client

import config

sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


def now():
    return datetime.now(timezone.utc).isoformat()


def requeue_stale(hours=3):
    """Si el worker murió a mitad, devuelve a la cola los jobs que llevan mucho 'running'."""
    limit = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    sb.table("jobs").update({"status": "queued"}).eq("status", "running").lt("locked_at", limit).execute()


def claim_job(types=("download", "record", "clip")):
    res = (sb.table("jobs").select("*").eq("status", "queued").in_("type", list(types))
           .order("created_at").limit(1).execute())
    if not res.data:
        return None
    job = res.data[0]
    upd = (sb.table("jobs")
           .update({"status": "running", "locked_at": now(), "attempts": job["attempts"] + 1})
           .eq("id", job["id"]).eq("status", "queued").execute())
    return upd.data[0] if upd.data else None  # vacío = otro worker lo tomó primero


def finish_job(job_id, ok=True):
    sb.table("jobs").update({"status": "done" if ok else "error"}).eq("id", job_id).execute()


def get_source(source_id):
    return sb.table("sources").select("*").eq("id", source_id).single().execute().data


def source_exists(source_id) -> bool:
    res = sb.table("sources").select("id").eq("id", source_id).limit(1).execute()
    return bool(res.data)


def set_source(source_id, **fields):
    sb.table("sources").update(fields).eq("id", source_id).execute()


def save_transcript(source_id, segments, batch=500):
    rows = [{"source_id": source_id, "start_sec": s["start"], "end_sec": s["end"], "text": s["text"]}
            for s in segments]
    for i in range(0, len(rows), batch):
        sb.table("transcript_segments").insert(rows[i : i + batch]).execute()


def save_rejected(source_id, rejected):
    rows = [{"source_id": source_id, **r} for r in rejected[:30]]
    if rows:
        sb.table("rejected_moments").insert(rows).execute()


def upload_clip(path, local_file):
    with open(local_file, "rb") as f:
        sb.storage.from_("clips").upload(path, f.read(), {"content-type": "video/mp4", "upsert": "true"})


_clipper_cache = {}


def _clipper_of(source):
    """Nombre público de quien creó la fuente (columna sources.clipper, migración 0004). Si no existe, None."""
    if source not in _clipper_cache:
        try:
            r = sb.table("sources").select("clipper").eq("id", source).maybe_single().execute()
            _clipper_cache[source] = (r.data or {}).get("clipper") if r else None
        except Exception:  # noqa: BLE001  (columna aún no creada)
            _clipper_cache[source] = None
    return _clipper_cache[source]


_extra_cols_ok = True   # pasa a False si la tabla clips aún no tiene description/hashtags (migración 0005)


def save_clip(source, user_id, m, storage_path, size_bytes, words_in_clip):
    global _extra_cols_ok
    row = {
        "source_id": source, "user_id": user_id, "title": m["title"], "clipper": _clipper_of(source),
        "start_sec": m["abs_start"], "end_sec": m["abs_end"], "viral_score": m["score"],
        "reason": m["reason"], "captions": words_in_clip,
        "storage_path": storage_path, "size_bytes": size_bytes,
    }
    extra = {}
    if m.get("description"):
        extra["description"] = m["description"]
    if m.get("hashtags"):
        extra["hashtags"] = m["hashtags"]
    if extra and _extra_cols_ok:
        try:
            sb.table("clips").insert({**row, **extra}).execute()
            return
        except Exception as e:  # noqa: BLE001
            _extra_cols_ok = False
            print(f"  Aviso: no pude guardar descripción/hashtags ({str(e)[:80]}). Ejecuta 0005_calidad.sql en Supabase.", flush=True)
    sb.table("clips").insert(row).execute()


def get_clip(clip_id):
    res = sb.table("clips").select("*").eq("id", clip_id).limit(1).execute()
    return res.data[0] if res.data else None


def update_clip(clip_id, **fields):
    sb.table("clips").update(fields).eq("id", clip_id).execute()


def remove_file(path):
    try:
        sb.storage.from_("clips").remove([path])
    except Exception:  # noqa: BLE001
        pass


_hb_warned = False


def heartbeat(info=None):
    """Avisa a la web que el worker está vivo (tabla worker_status). Nunca tumba al worker."""
    global _hb_warned
    try:
        sb.table("worker_status").upsert({"id": 1, "seen_at": now(), "info": info or {}}).execute()
    except Exception as e:  # noqa: BLE001
        if not _hb_warned:
            print(f"Aviso: no pude escribir worker_status ({e}). ¿Corriste 0003_live.sql?", flush=True)
            _hb_warned = True


def touch_job(job_id):
    """Renueva locked_at para que un directo largo no se considere 'muerto'."""
    sb.table("jobs").update({"locked_at": now()}).eq("id", job_id).execute()


def stop_requested(source_id) -> bool:
    res = sb.table("sources").select("stop_requested").eq("id", source_id).maybe_single().execute()
    return bool(res and res.data and res.data.get("stop_requested"))


def set_progress(source_id, **p):
    sb.table("sources").update({"progress": p}).eq("id", source_id).execute()


# ----------------------------------------------------------------------------- Parte 2: directos
_LIVE_ACTIVE = ["queued", "downloading", "recording", "transcribing", "analyzing", "clipping"]
_cmd_warned = False


def pending_commands(source_id):
    """Pedidos de 'Clip ahora' que la web dejó para este directo (tabla live_commands, migración 0006)."""
    global _cmd_warned
    try:
        res = (sb.table("live_commands").select("*").eq("source_id", source_id).eq("status", "pending")
               .order("created_at").limit(10).execute())
        return res.data or []
    except Exception as e:  # noqa: BLE001
        if not _cmd_warned:
            print(f"  Aviso: no pude leer live_commands ({str(e)[:80]}). Corre 0006_envivo.sql para activar 'Clip ahora'.", flush=True)
            _cmd_warned = True
        return []


def finish_command(cmd_id, ok=True, message=None, clip_id=None):
    fields = {"status": "done" if ok else "error", "message": (message or "")[:300], "done_at": now()}
    if clip_id:
        fields["clip_id"] = clip_id
    try:
        sb.table("live_commands").update(fields).eq("id", cmd_id).execute()
    except Exception:  # noqa: BLE001
        pass


def active_channels():
    return sb.table("watch_channels").select("*").eq("active", True).order("created_at").execute().data or []


def update_channel(channel_id, **fields):
    try:
        sb.table("watch_channels").update(fields).eq("id", channel_id).execute()
    except Exception:  # noqa: BLE001
        pass


def live_active() -> bool:
    """True si ya hay un directo en cola o grabando (el worker graba uno a la vez)."""
    res = sb.table("sources").select("id").eq("kind", "live").in_("status", _LIVE_ACTIVE).limit(1).execute()
    return bool(res.data)


def create_live_source(ch, found):
    """Crea la fuente y el trabajo de grabación para un canal que entró en vivo. Devuelve el id de la fuente."""
    options = {"content_type": ch.get("content_type") or "auto", "game": ch.get("game"),
               "progress_bar": bool(ch.get("progress_bar"))}
    row = {"kind": "live", "url": found["url"], "title": found.get("title"), "status": "queued",
           "layout": ch.get("layout") or "crop", "clipper": ch.get("clipper")}
    try:
        src = sb.table("sources").insert({**row, "options": options}).execute().data[0]
    except Exception:  # noqa: BLE001  (aún no existe la columna options)
        src = sb.table("sources").insert(row).execute().data[0]
    payload = {"clip_seconds": int(ch.get("clip_seconds") or 45), "quality": ch.get("quality") or "720p",
               "review_minutes": int(ch.get("review_minutes") or 2), **options}
    if ch.get("max_new"):
        payload["max_new"] = int(ch["max_new"])
    sb.table("jobs").insert({"source_id": src["id"], "type": "record", "payload": payload}).execute()
    return src["id"]
