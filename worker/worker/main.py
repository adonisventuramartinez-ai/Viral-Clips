"""Worker de ClipForge: toma jobs 'download' (videos) y 'record' (directos) y produce clips verticales."""
import shutil
import time
import traceback
import uuid

import config
import db
from analyze import find_moments
from download import download
import live
import selfcheck
from render import render_clip
from transcribe import transcribe


class Cancelled(Exception):
    """La fuente se quitó desde la web (botón Limpiar) mientras se procesaba."""


def process(job):
    sid = job["source_id"]
    src = db.get_source(sid)
    payload = job.get("payload") or {}
    n_clips = int(payload.get("clips", 15))
    secs = int(payload.get("clip_seconds", 45))
    quality = payload.get("quality", "1080p")

    def alive():
        if not db.source_exists(sid):
            raise Cancelled()

    work = config.WORK_DIR / sid
    work.mkdir(parents=True, exist_ok=True)
    try:
        db.set_source(sid, status="downloading", error=None)
        video, title, offset = download(src["url"], work, quality, src.get("range_from"), src.get("range_to"))
        alive()
        db.set_source(sid, title=title, status="transcribing")

        segments, words = transcribe(video, work)
        if not segments:
            raise RuntimeError("No se detectó voz en el video")
        # tiempos del archivo -> tiempos del video original, para guardar en la base
        db.save_transcript(sid, [{**s, "start": s["start"] + offset, "end": s["end"] + offset} for s in segments])

        alive()
        db.set_source(sid, status="analyzing")
        chosen, rejected = find_moments(segments, n_clips, secs)
        db.save_rejected(sid, rejected)
        if not chosen:
            raise RuntimeError("La IA no encontró momentos para clips")

        db.set_source(sid, status="clipping")
        for m in sorted(chosen, key=lambda x: x["start"]):
            alive()
            cid = str(uuid.uuid4())
            out = work / f"{cid}.mp4"
            render_clip(video, words, m["start"], m["end"], out, work)
            path = f"{sid}/{cid}.mp4"
            db.upload_clip(path, out)
            m["abs_start"], m["abs_end"] = m["start"] + offset, m["end"] + offset
            in_clip = [{"w": w["w"], "start": w["start"] - m["start"], "end": w["end"] - m["start"]}
                       for w in words if m["start"] <= w["start"] <= m["end"]]
            db.save_clip(sid, src.get("user_id"), m, path, out.stat().st_size, in_clip)
            out.unlink(missing_ok=True)
            print(f"  clip listo: {m['title']} ({m['score']}%)", flush=True)

        db.set_source(sid, status="done")
        db.finish_job(job["id"], ok=True)
    except Cancelled:
        print(f"  fuente {sid} quitada desde la web, cancelo.", flush=True)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        db.set_source(sid, status="error", error=f"{type(e).__name__}: {e}"[:500])
        db.finish_job(job["id"], ok=False)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        raise SystemExit("Falta SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
    selfcheck.run()
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    import llm
    print(f"IA en orden de uso: {' → '.join(llm.configured())}", flush=True)
    print("Worker listo, esperando trabajos…", flush=True)
    last_clean = 0.0
    while True:
        db.heartbeat()
        if time.time() - last_clean > 600:
            db.requeue_stale()
            last_clean = time.time()
        job = db.claim_job()
        if job:
            print(f"Trabajo {job['id']} → fuente {job['source_id']}", flush=True)
            if job["type"] == "record":
                live.process_live(job)
            else:
                process(job)
        else:
            time.sleep(config.POLL_SECONDS)


if __name__ == "__main__":
    main()
