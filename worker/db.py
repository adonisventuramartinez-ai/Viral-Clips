from datetime import datetime, timedelta, timezone

from supabase import create_client

import config

sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


def now():
    return datetime.now(timezone.utc).isoformat()


def requeue_stale(hours=3):
    """Si el worker murió a mitad, devuelve a la cola los jobs que llevan mucho 'running'.
    Si ya agotaron sus intentos (algo los tumba siempre), los deja en error en vez de repetirlos para siempre."""
    limit = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = sb.table("jobs").select("id,attempts,source_id").eq("status", "running").lt("locked_at", limit).execute().data or []
    for r in rows:
        if int(r.get("attempts") or 0) >= config.JOB_MAX_ATTEMPTS:
            finish_job(r["id"], ok=False, error="El worker se detuvo varias veces con este trabajo")
            try:
                set_source(r["source_id"], status="error", error="El trabajo se interrumpió varias veces. Vuelve a intentarlo.")
            except Exception:  # noqa: BLE001
                pass
        else:
            sb.table("jobs").update({"status": "queued", "locked_at": None}).eq("id", r["id"]).execute()


_queue_cols_ok = True   # pasa a False si jobs aún no tiene priority/run_after (migración 0008)


def claim_job(types=("download", "record", "clip")):
    """Toma el trabajo más urgente: primero prioridad alta, luego el más antiguo; salta los que esperan un reintento."""
    global _queue_cols_ok
    res = None
    if _queue_cols_ok:
        try:
            res = (sb.table("jobs").select("*").eq("status", "queued").in_("type", list(types))
                   .or_(f"run_after.is.null,run_after.lte.{now()}")
                   .order("priority", desc=True).order("created_at").limit(1).execute())
        except Exception as e:  # noqa: BLE001
            _queue_cols_ok = False
            print(f"Aviso: la cola no pudo usar prioridades/reintentos ({str(e)[:80]}). Ejecuta 0008_cola.sql en Supabase.", flush=True)
    if res is None:
        res = (sb.table("jobs").select("*").eq("status", "queued").in_("type", list(types))
               .order("created_at").limit(1).execute())
    if not res.data:
        return None
    job = res.data[0]
    upd = (sb.table("jobs")
           .update({"status": "running", "locked_at": now(), "attempts": job["attempts"] + 1})
           .eq("id", job["id"]).eq("status", "queued").execute())
    return upd.data[0] if upd.data else None  # vacío = otro worker lo tomó primero


def finish_job(job_id, ok=True, error=None):
    fields = {"status": "done" if ok else "error"}
    if error and _queue_cols_ok:
        fields["last_error"] = str(error)[:500]
    try:
        sb.table("jobs").update(fields).eq("id", job_id).execute()
    except Exception:  # noqa: BLE001  (columna last_error aún no creada)
        sb.table("jobs").update({"status": fields["status"]}).eq("id", job_id).execute()


def retry_job(job_id, delay_seconds, error=None):
    """Devuelve el trabajo a la cola para dentro de `delay_seconds`. Sin la migración 0008 se reintenta ya mismo."""
    fields = {"status": "queued", "locked_at": None}
    if _queue_cols_ok:
        fields["run_after"] = (datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)).isoformat()
        if error:
            fields["last_error"] = str(error)[:500]
    try:
        sb.table("jobs").update(fields).eq("id", job_id).execute()
    except Exception:  # noqa: BLE001
        sb.table("jobs").update({"status": "queued", "locked_at": None}).eq("id", job_id).execute()


def reset_source_outputs(source_id):
    """Antes de repetir un trabajo: borra lo que dejó el intento anterior (transcripción, descartados y clips a medias)
    para que el reintento no duplique nada."""
    rows = sb.table("clips").select("id,storage_path,thumb_path,publish_status").eq("source_id", source_id).execute().data or []
    keep = [r for r in rows if r.get("publish_status") in ("published", "scheduled")]   # lo ya publicado o programado no se toca
    drop = [r for r in rows if r not in keep]
    paths = [p for r in drop for p in (r.get("storage_path"), r.get("thumb_path")) if p]
    if paths:
        try:
            sb.storage.from_("clips").remove(paths)
        except Exception:  # noqa: BLE001
            pass
    for r in drop:
        sb.table("clips").delete().eq("id", r["id"]).execute()
    sb.table("transcript_segments").delete().eq("source_id", source_id).execute()
    sb.table("rejected_moments").delete().eq("source_id", source_id).execute()
    return len(drop)


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


_pack_cols_ok = True   # pasa a False si la tabla clips aún no tiene pack/thumb_path (migración 0007)


def save_clip(source, user_id, m, storage_path, size_bytes, words_in_clip):
    global _extra_cols_ok, _pack_cols_ok
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
    pack = {}
    if m.get("pack"):
        pack["pack"] = m["pack"]
    if m.get("thumb_path"):
        pack["thumb_path"] = m["thumb_path"]
    if pack and _pack_cols_ok:
        try:
            sb.table("clips").insert({**row, **extra, **pack}).execute()
            return
        except Exception as e:  # noqa: BLE001
            _pack_cols_ok = False
            print(f"  Aviso: no pude guardar paquete/miniatura ({str(e)[:80]}). Ejecuta 0007_publicacion.sql en Supabase.", flush=True)
    if extra and _extra_cols_ok:
        try:
            sb.table("clips").insert({**row, **extra}).execute()
            return
        except Exception as e:  # noqa: BLE001
            _extra_cols_ok = False
            print(f"  Aviso: no pude guardar descripción/hashtags ({str(e)[:80]}). Ejecuta 0005_calidad.sql en Supabase.", flush=True)
    sb.table("clips").insert(row).execute()


def upload_thumb(path, local_file):
    with open(local_file, "rb") as f:
        sb.storage.from_("clips").upload(path, f.read(), {"content-type": "image/jpeg", "upsert": "true"})


def download_clip(path):
    return sb.storage.from_("clips").download(path)


def due_clips(limit=5):
    """Clips programados cuya hora ya llegó (lista vacía si la migración 0007 no se ha corrido)."""
    try:
        from datetime import datetime, timezone
        res = (sb.table("clips").select("id,title,storage_path,description,hashtags,pack,scheduled_at,publish_status")
               .eq("publish_status", "scheduled").lte("scheduled_at", datetime.now(timezone.utc).isoformat())
               .order("scheduled_at").limit(limit).execute())
        return res.data or []
    except Exception:  # noqa: BLE001
        return []


def recent_clip_texts(user_id, hours=48, limit=80):
    """Textos hablados de los clips que este usuario creó en las últimas `hours` horas (para no repetir el mismo momento
    visto desde otra cámara). Lista vacía si algo falla."""
    try:
        from datetime import datetime, timedelta, timezone
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        q = sb.table("clips").select("captions").gte("created_at", since).order("created_at", desc=True).limit(limit)
        if user_id:
            q = q.eq("user_id", user_id)
        out = []
        for row in (q.execute().data or []):
            caps = row.get("captions") or []
            txt = " ".join(str(c.get("w", "")) for c in caps if isinstance(c, dict)).strip()
            if txt:
                out.append(txt)
        return out
    except Exception:  # noqa: BLE001
        return []


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
    payload = {"clip_seconds": int(ch.get("clip_seconds") or 0),   # 0 = automática (largo ideal del tipo) "quality": ch.get("quality") or "720p",
               "review_minutes": int(ch.get("review_minutes") or 2), **options}
    if ch.get("max_new"):
        payload["max_new"] = int(ch["max_new"])
    try:
        sb.table("jobs").insert({"source_id": src["id"], "type": "record", "payload": payload, "priority": 10}).execute()
    except Exception:  # noqa: BLE001  (aún no existe la columna priority: migración 0008)
        sb.table("jobs").insert({"source_id": src["id"], "type": "record", "payload": payload}).execute()
    return src["id"]
