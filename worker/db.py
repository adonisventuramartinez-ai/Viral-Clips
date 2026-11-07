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


def claim_job(types=("download",)):
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


def save_clip(source, user_id, m, storage_path, size_bytes, words_in_clip):
    sb.table("clips").insert({
        "source_id": source, "user_id": user_id, "title": m["title"],
        "start_sec": m["abs_start"], "end_sec": m["abs_end"], "viral_score": m["score"],
        "reason": m["reason"], "captions": words_in_clip,
        "storage_path": storage_path, "size_bytes": size_bytes,
    }).execute()
