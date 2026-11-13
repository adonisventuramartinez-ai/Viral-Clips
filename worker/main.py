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
import rerender
import selfcheck
import watcher
import brand
import energy
import profiles
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
    # Opciones de contenido: lo que mandó la web en el trabajo manda sobre lo guardado en la fuente
    opts = {**(src.get("options") or {}), **{k: v for k, v in payload.items() if v is not None}}
    prof = profiles.get(opts.get("content_type"))
    game = opts.get("game")
    print(f"  Tipo de contenido: {prof['label']}" + (f" · juego: {game}" if game else ""), flush=True)

    # Encuadre elegido en la web: crop | split | blur y, si lo marcó a mano, el recuadro en % del video
    clip_layout = src.get("layout") or config.CLIP_LAYOUT
    custom_crop = src.get("custom_crop")
    if "layout" not in src:
        print("  AVISO: la tabla sources no tiene la columna 'layout'. Ejecuta 0004_comunidad.sql en Supabase.", flush=True)
    print(f"  Encuadre pedido: {clip_layout} | recuadro manual: {'sí' if custom_crop else 'no (automático)'}", flush=True)

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
        
        db.save_transcript(sid, [{**s, "start": s["start"] + offset, "end": s["end"] + offset} for s in segments])

        alive()
        db.set_source(sid, status="analyzing")
        ai_segments = segments
        try:
            dur_v = segments[-1]["end"]
            loud = energy.loud_seconds(video)
            motion = energy.motion_seconds(video) if prof["bonus"].get("motion") else set()
            chat = energy.chat_seconds(src["url"], work, offset, dur_v)
            n_hot = energy.annotate(segments, loud, chat, motion)
            print(f"  Pistas: {len(loud)} s con volumen alto, {len(motion)} s de acción en pantalla, {n_hot} frase(s) marcada(s)", flush=True)
            if prof.get("action"):
                ai_segments = energy.add_action_markers(segments, loud, motion, chat)
        except Exception as e:  # noqa: BLE001  (las pistas son un extra: nunca deben tumbar el trabajo)
            print(f"  Pistas: no pude calcularlas ({type(e).__name__}: {e})", flush=True)
        chosen, rejected = find_moments(ai_segments, n_clips, secs, words=words, profile=prof, game=game)
        db.save_rejected(sid, rejected)
        if not chosen:
            raise RuntimeError("La IA no encontró momentos para clips")

        db.set_source(sid, status="clipping")
        logo = brand.load(work)
        logo["progress_bar"] = bool(opts.get("progress_bar"))
        for m in sorted(chosen, key=lambda x: x["start"]):
            alive()
            cid = str(uuid.uuid4())
            out = work / f"{cid}.mp4"
            
            render_clip(video, words, m["start"], m["end"], out, work, custom_crop=custom_crop, layout=clip_layout, brand=logo,
                        hook=m.get("hook") or m["title"])
            
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
    print("Worker listo (encuadres: vertical, dividido, dos personas, difuminado; directos con reconexión y chat), esperando trabajos…", flush=True)
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
            elif job["type"] == "clip":
                rerender.process_rerender(job)
            else:
                process(job)
        else:
            try:
                watcher.tick()      # ¿alguno de tus canales entró en vivo? (solo cuando el worker está libre)
            except Exception as e:  # noqa: BLE001  (vigilar canales es un extra: nunca debe tumbar al worker)
                print(f"Canales automáticos: error ({type(e).__name__}: {str(e)[:100]})", flush=True)
            time.sleep(config.POLL_SECONDS)


if __name__ == "__main__":
    main()
