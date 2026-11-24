from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def claim_job(types=("download", "record", "clip", "transform", "text_to_video", "search")):
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


# ----------------------------------------------------------------------------- Modo Transformar (bucket 'uploads')
def upload_input(path, local_file):
    """Guarda el video que subió la persona (lo usa la web; el worker solo lo lee)."""
    with open(local_file, "rb") as f:
        sb.storage.from_("uploads").upload(path, f.read(), {"content-type": "video/mp4", "upsert": "true"})


def input_signed_url(path, seconds=86400):
    """URL temporal para descargar el video subido (24 h por defecto, por si el worker va detrás)."""
    try:
        r = sb.storage.from_("uploads").create_signed_url(path, seconds)
        u = r.get("signedURL") or r.get("signed_url") or r.get("signedUrl")
        if u and not u.startswith("http"):
            u = f"{config.SUPABASE_URL.rstrip('/')}/storage/v1{u if u.startswith('/') else '/' + u}"
        return u
    except Exception:  # noqa: BLE001  (el worker usa download_input: la URL es solo un respaldo)
        return None


def download_input(path, dest):
    """Baja el video original del bucket 'uploads' al directorio de trabajo del worker."""
    dest = Path(dest)
    data = sb.storage.from_("uploads").download(path)
    if not data:
        raise RuntimeError(f"No se pudo descargar el archivo subido ({path})")
    dest.write_bytes(data)
    return dest


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
    """Guarda el clip y devuelve su id. Va quitando columnas nuevas que la base aún no tenga (migraciones 0005, 0007, 0009)."""
    global _extra_cols_ok, _pack_cols_ok, _viral_cols_ok
    row = {
        "source_id": source, "user_id": user_id, "title": m["title"], "clipper": _clipper_of(source),
        "start_sec": m["abs_start"], "end_sec": m["abs_end"], "viral_score": m["score"],
        "reason": m["reason"], "captions": words_in_clip,
        "storage_path": storage_path, "size_bytes": size_bytes,
    }
    extra = {k: m[k] for k in ("description", "hashtags") if m.get(k)}
    pack = {k: m[k] for k in ("pack", "thumb_path") if m.get(k)}
    viral = {}
    if m.get("viral"):
        viral = {"viral": m["viral"], "viral_status": m.get("viral_status") or "pending"}
    if m.get("thumb_b_path"):
        viral["thumb_b_path"] = m["thumb_b_path"]
    tries = []
    if viral and _viral_cols_ok:
        tries.append(("viral", {**row, **extra, **pack, **viral}))
    if pack and _pack_cols_ok:
        tries.append(("pack", {**row, **extra, **pack}))
    if extra and _extra_cols_ok:
        tries.append(("extra", {**row, **extra}))
    tries.append(("base", row))
    for kind, data in tries:
        try:
            res = sb.table("clips").insert(data).execute()
            return (res.data or [{}])[0].get("id")
        except Exception as e:  # noqa: BLE001
            if kind == "base":
                raise
            if kind == "viral":
                _viral_cols_ok = False
                print(f"  Aviso: no pude guardar el análisis viral ({str(e)[:80]}). Ejecuta 0009_viral.sql en Supabase.", flush=True)
            elif kind == "pack":
                _pack_cols_ok = False
                print(f"  Aviso: no pude guardar paquete/miniatura ({str(e)[:80]}). Ejecuta 0007_publicacion.sql en Supabase.", flush=True)
            else:
                _extra_cols_ok = False
                print(f"  Aviso: no pude guardar descripción/hashtags ({str(e)[:80]}). Ejecuta 0005_calidad.sql en Supabase.", flush=True)


_viral_cols_ok = True   # pasa a False si clips aún no tiene viral/viral_status (migración 0009)


def clips_needing_viral(limit=3):
    """Clips recientes que aún no pasaron por el área viral (en vivo, rehechos). Vacío si falta la migración 0009."""
    global _viral_cols_ok
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=config.VIRAL_BACKFILL_DAYS)).isoformat()
        res = (sb.table("clips").select("id,title,viral_score,hashtags,captions,start_sec,end_sec")
               .eq("viral_status", "pending").gte("created_at", since).order("created_at").limit(limit).execute())
        return res.data or []
    except Exception:  # noqa: BLE001
        return []


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


BASE_INFO = {}   # datos fijos que siempre van en el latido (redes configuradas, cola automática)


def heartbeat(info=None):
    """Avisa a la web que el worker está vivo (tabla worker_status). Nunca tumba al worker."""
    global _hb_warned
    try:
        sb.table("worker_status").upsert({"id": 1, "seen_at": now(), "info": {**BASE_INFO, **(info or {})}}).execute()
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
    payload = {"clip_seconds": int(ch.get("clip_seconds") or 0),   # 0 = automática (largo ideal del tipo)
               "quality": ch.get("quality") or "720p",
               "review_minutes": int(ch.get("review_minutes") or 2), **options}
    if ch.get("max_new"):
        payload["max_new"] = int(ch["max_new"])
    try:
        sb.table("jobs").insert({"source_id": src["id"], "type": "record", "payload": payload, "priority": 10}).execute()
    except Exception:  # noqa: BLE001  (aún no existe la columna priority: migración 0008)
        sb.table("jobs").insert({"source_id": src["id"], "type": "record", "payload": payload}).execute()
    return src["id"]


# ----------------------------------------------------------------------------- Parte 8: cola de publicación (tabla posts, migración 0010)
def signed_url(path, seconds=3600):
    r = sb.storage.from_("clips").create_signed_url(path, seconds)
    u = r.get("signedURL") or r.get("signed_url") or r.get("signedUrl")
    if u and not u.startswith("http"):
        u = f"{config.SUPABASE_URL.rstrip('/')}/storage/v1{u if u.startswith('/') else '/' + u}"
    return u


def clips_ready_for_queue(networks, limit=10):
    """Clips 'listos' o aprobados (solo aprobados si pediste aprobar tú cada uno en Hacerlo viral), recientes, con archivo, sin publicar/programar a mano y sin post en alguna de las redes pedidas."""
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=config.QUEUE_CLIP_DAYS)).isoformat()
        rows = (sb.table("clips").select("id,title,viral,viral_score,viral_status,publish_status,storage_path")
                .in_("viral_status", ["approved"] if require_approval() else ["ready", "approved"]).gte("created_at", since).not_.is_("storage_path", "null")
                .order("created_at", desc=True).limit(60).execute().data or [])
        rows = [r for r in rows if r.get("publish_status") not in ("scheduled", "published")]
        if not rows:
            return []
        have = {}
        for p in sb.table("posts").select("clip_id,network").in_("clip_id", [r["id"] for r in rows]).execute().data or []:
            have.setdefault(p["clip_id"], set()).add(p["network"])
        return [r for r in rows if set(networks) - have.get(r["id"], set()) == set(networks)][:limit]
    except Exception:  # noqa: BLE001
        return []


def posts_taken(networks):
    """{red: [fechas ya ocupadas]} (incluye lo programado a mano en Facebook desde la tarjeta del clip)."""
    out = {n: [] for n in networks}
    try:
        for p in sb.table("posts").select("network,scheduled_at").in_("status", ["queued", "publishing"]).execute().data or []:
            out.setdefault(p["network"], []).append(p["scheduled_at"])
        if "facebook" in out:
            for c in sb.table("clips").select("scheduled_at").eq("publish_status", "scheduled").execute().data or []:
                out["facebook"].append(c["scheduled_at"])
    except Exception:  # noqa: BLE001
        pass
    return out


def posts_pending(networks):
    out = {n: 0 for n in networks}
    try:
        for p in sb.table("posts").select("network").eq("status", "queued").execute().data or []:
            out[p["network"]] = out.get(p["network"], 0) + 1
    except Exception:  # noqa: BLE001
        pass
    return out


def create_posts(rows):
    sb.table("posts").upsert([{**r, "status": "queued"} for r in rows], on_conflict="clip_id,network", ignore_duplicates=True).execute()


def due_posts(limit=5):
    try:
        res = (sb.table("posts").select("*").eq("status", "queued").lte("scheduled_at", now())
               .order("scheduled_at").limit(limit).execute())
        return res.data or []
    except Exception:  # noqa: BLE001  (migración 0010 sin correr)
        return []


def claim_post(post_id):
    """Reserva el post (queued -> publishing). False si otro ya lo tomó o ya no está en cola."""
    res = (sb.table("posts").update({"status": "publishing", "attempts": 1}).eq("id", post_id).eq("status", "queued").execute())
    return bool(res.data)


def update_post(post_id, **fields):
    sb.table("posts").update(fields).eq("id", post_id).execute()


def recover_posts():
    """Al arrancar: todo post en 'publishing' quedó a medias (el worker se cayó). Se marca en error y NO se repite solo, para no publicar doble."""
    sb.table("posts").update({"status": "error", "error": "Interrumpido mientras publicaba. Revisa tu página antes de reintentar."}) \
        .eq("status", "publishing").execute()


# ----------------------------------------------------------------------------- Parte 9: clips automáticos (migración 0011)
def due_feeds(minutes):
    """Fuentes activas que ya toca revisar (nunca revisadas, o hace más de `minutes`)."""
    limit = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    return (sb.table("discover_feeds").select("*").eq("active", True)
            .or_(f"last_checked.is.null,last_checked.lte.{limit}").order("last_checked", nullsfirst=True).limit(10).execute().data or [])


def update_feed(feed_id, **fields):
    try:
        sb.table("discover_feeds").update(fields).eq("id", feed_id).execute()
    except Exception:  # noqa: BLE001
        pass


def known_video_ids(feed_id, ids):
    if not ids:
        return set()
    rows = sb.table("discovered_videos").select("video_id").eq("feed_id", feed_id).in_("video_id", list(ids)).execute().data or []
    return {r["video_id"] for r in rows}


def discovered_today():
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    res = sb.table("discovered_videos").select("id", count="exact").eq("status", "queued").gte("created_at", since).execute()
    return int(res.count or 0)


def videos_waiting():
    """Videos (no directos) todavía en proceso: así no se apila trabajo."""
    res = (sb.table("sources").select("id", count="exact").eq("kind", "vod_url")
           .in_("status", ["queued", "downloading", "transcribing", "analyzing", "clipping"]).execute())
    return int(res.count or 0)


def url_already_used(url):
    if not url:
        return False
    return bool(sb.table("sources").select("id").eq("url", url).limit(1).execute().data)


def remember_video(feed_id, info, status, reason=None, source_id=None):
    row = {"feed_id": feed_id, "video_id": str(info.get("id")), "title": (info.get("title") or "")[:200],
           "url": info.get("webpage_url"), "views": int(info.get("view_count") or 0), "status": status,
           "reason": reason, "source_id": source_id}
    try:
        sb.table("discovered_videos").upsert(row, on_conflict="feed_id,video_id").execute()
    except Exception:  # noqa: BLE001
        pass


def create_vod_source(feed, info):
    """Igual que pegar el link en Crear clips: fuente + trabajo de descarga. Devuelve el id de la fuente."""
    url = info.get("webpage_url") or f"https://www.youtube.com/watch?v={info['id']}"
    options = {"content_type": feed.get("content_type") or "auto", "game": feed.get("game"), "progress_bar": False}
    row = {"kind": "vod_url", "url": url, "title": info.get("title"), "status": "queued",
           "layout": feed.get("layout") or "crop", "clipper": feed.get("clipper")}
    try:
        src = sb.table("sources").insert({**row, "options": options}).execute().data[0]
    except Exception:  # noqa: BLE001  (aún no existe la columna options)
        src = sb.table("sources").insert(row).execute().data[0]
    payload = {"clip_seconds": 0, "clips": int(feed.get("clips") or 4), "quality": feed.get("quality") or "720p", "review_minutes": 2, **options}
    sb.table("jobs").insert({"source_id": src["id"], "type": "download", "payload": payload}).execute()
    remember_video(feed["id"], info, "queued", None, src["id"])
    return src["id"]


# ----------------------------------------------------------------------------- Buscador TikTok/Reels (migración 0019)
def get_search(search_id):
    res = sb.table("clip_searches").select("*").eq("id", search_id).maybe_single().execute()
    return (res.data if res else None) or None


def update_search(search_id, **fields):
    """Actualiza una búsqueda sin tumbar el trabajo si la tabla aún no tiene alguna columna."""
    try:
        sb.table("clip_searches").update(fields).eq("id", search_id).execute()
    except Exception as e:  # noqa: BLE001
        print(f"Buscador: no pude actualizar la búsqueda ({str(e)[:100]})", flush=True)


def save_search_results(rows, batch=200):
    """Guarda (o actualiza) los hallazgos. `rows` = [{search_id, network, video_id, ...}]."""
    for i in range(0, len(rows), batch):
        sb.table("clip_search_results").upsert(rows[i : i + batch], on_conflict="search_id,network,video_id").execute()


def search_known_urls(urls):
    urls = [u for u in urls if u]
    if not urls:
        return set()
    found = set()
    for i in range(0, len(urls), 100):
        rows = sb.table("sources").select("url").in_("url", urls[i : i + 100]).execute().data or []
        found |= {r.get("url") for r in rows}
    return found


def get_search_result(result_id):
    res = sb.table("clip_search_results").select("*").eq("id", result_id).maybe_single().execute()
    return (res.data if res else None) or None


def update_search_result(result_id, **fields):
    try:
        sb.table("clip_search_results").update(fields).eq("id", result_id).execute()
    except Exception as e:  # noqa: BLE001
        print(f"Buscador: no pude actualizar el resultado ({str(e)[:100]})", flush=True)


def create_search_source(info, opts, search_id=None, result_id=None):
    """Encola el video encontrado como si lo hubieras pegado en Crear clips. Devuelve el id de la fuente."""
    url = info.get("url") or info.get("webpage_url")
    if not url:
        raise RuntimeError("el video encontrado no tiene link")
    existing = sb.table("sources").select("id").eq("url", url).limit(1).execute().data or []
    if existing:
        sid = existing[0]["id"]
    else:
        options = {"content_type": opts.get("content_type") or "auto", "game": None, "progress_bar": False}
        row = {"kind": "vod_url", "url": url, "title": (info.get("title") or "")[:200], "status": "queued",
               "layout": "crop", "video_id": str(info.get("video_id") or ""), "search_id": search_id}
        try:
            sid = sb.table("sources").insert({**row, "options": options}).execute().data[0]["id"]
        except Exception:  # noqa: BLE001  (columnas nuevas aún no creadas)
            row.pop("video_id", None)
            row.pop("search_id", None)
            try:
                sid = sb.table("sources").insert({**row, "options": options}).execute().data[0]["id"]
            except Exception:
                sid = sb.table("sources").insert(row).execute().data[0]["id"]
    payload = {"clip_seconds": 0, "clips": int(opts.get("clips") or 4), "quality": opts.get("quality") or "1080p",
               "content_type": opts.get("content_type") or "auto", "original": True, "publish_fb": bool(opts.get("publish_fb", True))}
    # Si ya hay un trabajo de descarga para esa fuente, no duplicamos.
    pending = (sb.table("jobs").select("id").eq("source_id", sid).eq("type", "download")
               .in_("status", ["queued", "running"]).limit(1).execute().data or [])
    if not pending:
        sb.table("jobs").insert({"source_id": sid, "type": "download", "payload": payload, "priority": 0}).execute()
    if result_id:
        update_search_result(result_id, status="queued", source_id=sid)
    return sid


# ----------------------------------------------------------------------------- Parte 10: Mi página (migración 0012)
def published_items(days=30):
    """Lo que ya se publicó: la cola (posts) y lo programado a mano en Facebook (clips.fb_video_id), sin repetir."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    out, seen = [], set()
    try:
        for p in (sb.table("posts").select("id,clip_id,network,external_id,published_at").eq("status", "published")
                  .gte("published_at", since).not_.is_("external_id", "null").limit(1000).execute().data or []):
            key = (p["network"], str(p["external_id"]))
            if key not in seen:
                seen.add(key)
                out.append({"network": p["network"], "external_id": str(p["external_id"]), "post_id": p["id"],
                            "clip_id": p["clip_id"], "published_at": p["published_at"]})
    except Exception:  # noqa: BLE001
        pass
    try:
        for c in (sb.table("clips").select("id,fb_video_id,published_at").eq("publish_status", "published")
                  .gte("published_at", since).not_.is_("fb_video_id", "null").limit(1000).execute().data or []):
            key = ("facebook", str(c["fb_video_id"]))
            if key not in seen:
                seen.add(key)
                out.append({"network": "facebook", "external_id": str(c["fb_video_id"]), "post_id": None,
                            "clip_id": c["id"], "published_at": c["published_at"]})
    except Exception:  # noqa: BLE001
        pass
    return out


def stats_map():
    try:
        rows = sb.table("post_stats").select("*").limit(5000).execute().data or []
    except Exception:  # noqa: BLE001  (migración 0012 sin correr)
        return {}
    return {(r["network"], str(r["external_id"])): r for r in rows}


def save_stats(rows):
    sb.table("post_stats").upsert(rows, on_conflict="network,external_id").execute()


def stats_for_learning(days=60):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        return sb.table("post_stats").select("network,published_at,views,likes,comments,shares").gte("published_at", since).limit(5000).execute().data or []
    except Exception:  # noqa: BLE001
        return []


def save_best_hours(network, rows):
    """Reemplaza las horas aprendidas de esa red."""
    try:
        sb.table("best_hours").delete().eq("network", network).execute()
        if rows:
            stamp = now()
            sb.table("best_hours").insert([{**r, "network": network, "updated_at": stamp} for r in rows]).execute()
    except Exception:  # noqa: BLE001
        pass


def learned_slots(networks):
    """{red: ['12:30', ...]} con las horas aprendidas; si una red no tiene las suyas usa las de 'all'. Vacío = usar POST_SLOTS."""
    try:
        rows = sb.table("best_hours").select("network,slot").eq("chosen", True).execute().data or []
    except Exception:  # noqa: BLE001
        return {}
    by = {}
    for r in rows:
        by.setdefault(r["network"], []).append(r["slot"])
    return {n: sorted(by.get(n) or by.get("all") or []) for n in networks if by.get(n) or by.get("all")}


def save_followers(network, followers):
    day = datetime.now(timezone(timedelta(hours=config.POST_TZ_OFFSET))).date().isoformat()
    try:
        sb.table("page_followers").upsert({"network": network, "day": day, "followers": int(followers)}, on_conflict="network,day").execute()
    except Exception:  # noqa: BLE001
        pass


# ----------------------------------------------------------------------------- Conectar cuentas (migración 0013)
_conn_at = 0.0


def apply_connections(force=False, every=120):
    """Lee las llaves guardadas desde la web y las pone en config. Sin la tabla o sin llaves, no hace nada."""
    global _conn_at
    import time
    if not force and time.time() - _conn_at < every:
        return {}
    _conn_at = time.time()
    try:
        rows = sb.table("connections").select("network,data").execute().data or []
    except Exception:  # noqa: BLE001  (migración 0013 sin correr)
        return {}
    import connections
    return connections.apply(rows)


# ----------------------------------------------------------------------------- Parte 11: siempre activo
def recover_on_start():
    """Al arrancar el contenedor: los trabajos de video/clip que quedaron 'running' por un reinicio vuelven a la cola YA (no esperan 3 h).
    Los directos (record) no se tocan: un directo que se cortó no se puede retomar. Devuelve cuántos devolvió."""
    rows = sb.table("jobs").select("id,attempts,source_id,type").eq("status", "running").in_("type", ["download", "clip", "transform", "text_to_video"]).execute().data or []
    n = 0
    for r in rows:
        if int(r.get("attempts") or 0) >= config.JOB_MAX_ATTEMPTS:
            finish_job(r["id"], ok=False, error="El worker se detuvo varias veces con este trabajo")
            try:
                set_source(r["source_id"], status="error", error="El trabajo se interrumpió varias veces. Vuelve a intentarlo.")
            except Exception:  # noqa: BLE001
                pass
        else:
            sb.table("jobs").update({"status": "queued", "locked_at": None}).eq("id", r["id"]).execute()
            n += 1
    return n


def restart_is_safe(minutes=10):
    """True si no hay nada publicándose ni programado para los próximos `minutes`, ni un directo grabando. Si no se puede saber, False."""
    soon = (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()
    if sb.table("posts").select("id", count="exact").eq("status", "publishing").execute().count:
        return False
    if sb.table("posts").select("id", count="exact").eq("status", "queued").lte("scheduled_at", soon).execute().count:
        return False
    if sb.table("clips").select("id", count="exact").eq("publish_status", "scheduled").lte("scheduled_at", soon).execute().count:
        return False
    return not live_active()


# ----------------------------------------------------------------------------- Parte 12: página Hacerlo viral (migración 0014)
_vconf = {"at": 0.0, "val": None}


def require_approval():
    """¿Hay que aprobar a mano cada clip en Hacerlo viral antes de que entre a la cola? Lee el ajuste de la web (tabla viral_config),
    con VIRAL_REQUIRE_APPROVAL como respaldo si la tabla no existe. Se recuerda 20 s."""
    import time as _t
    if _t.time() - _vconf["at"] < 20 and _vconf["val"] is not None:
        return _vconf["val"]
    val = bool(config.VIRAL_REQUIRE_APPROVAL)
    try:
        rows = sb.table("viral_config").select("require_approval").eq("id", 1).limit(1).execute().data or []
        if rows:
            val = bool(rows[0].get("require_approval"))
    except Exception:  # noqa: BLE001  (sin la migración 0014 se usa el respaldo)
        pass
    _vconf["at"], _vconf["val"] = _t.time(), val
    return val


def clips_with_requests(limit=3):
    """Clips con un pedido de la web esperando (viral_req con acción y sin error). Vacío si falta la migración 0014."""
    try:
        rows = (sb.table("clips").select("*").not_.is_("viral_req", "null").order("created_at").limit(20).execute().data or [])
        return [r for r in rows if isinstance(r.get("viral_req"), dict) and r["viral_req"].get("action") and not r["viral_req"].get("error")][:limit]
    except Exception:  # noqa: BLE001
        return []


def clips_missing_thumbs(limit=2):
    """Clips ya analizados, con archivo y sin miniatura (llegaron en vivo o rehechos), que aún no se intentaron."""
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=config.VIRAL_BACKFILL_DAYS)).isoformat()
        rows = (sb.table("clips").select("*").is_("thumb_path", "null").not_.is_("storage_path", "null").not_.is_("viral", "null")
                .gte("created_at", since).order("created_at", desc=True).limit(20).execute().data or [])
        return [r for r in rows if not (r.get("viral") or {}).get("thumb_tried") and r.get("viral_req") is None][:limit]
    except Exception:  # noqa: BLE001
        return []


def cover_path(clip):
    """Ruta de la miniatura elegida para publicar (la B solo si la elegiste y existe)."""
    if (clip or {}).get("thumb_choice") == "b" and clip.get("thumb_b_path"):
        return clip["thumb_b_path"]
    return (clip or {}).get("thumb_path") or None



# ----------------------------------------------------------------------------- Parte 13: interruptores desde la web (migración 0015)
_sw = {"at": 0.0, "row": {}}


def web_switches(every=15):
    """Interruptores que dejaste en la web (tabla app_switches). Cada uno es True, False o None (None = lo que diga worker/.env).
    Se recuerdan 15 s. Sin la migración 0015 devuelve {} y todo sigue mandando el .env."""
    import time as _t
    if _t.time() - _sw["at"] < every:
        return _sw["row"]
    row = {}
    try:
        rows = sb.table("app_switches").select("discover,auto_queue").eq("id", 1).limit(1).execute().data or []
        if rows:
            row = rows[0]
    except Exception:  # noqa: BLE001  (sin la migración 0015: manda el .env)
        row = {}
    _sw["at"], _sw["row"] = _t.time(), row
    return row


def switch_on(name, default):
    """Valor efectivo de un interruptor: lo de la web si lo tocaste; si no, el valor del .env (`default`)."""
    v = (web_switches() or {}).get(name)
    return bool(default) if v is None else bool(v)


def discover_on():
    """¿Están encendidos los Clips automáticos? Botón de la web, o DISCOVER del .env si nunca lo tocaste."""
    return switch_on("discover", config.DISCOVER)


def auto_queue_on():
    """¿Está encendida la Cola automática? Botón de la web, o AUTO_QUEUE del .env si nunca lo tocaste."""
    return switch_on("auto_queue", config.AUTO_QUEUE)
