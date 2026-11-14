"""Re-render de un clip ya creado (botón "Ajustar" en la Biblioteca): otro inicio/fin y/u otro encuadre.
Como el video original no se guarda, baja solo ese tramo (+4 s de margen), lo transcribe de nuevo y lo corta."""
import shutil
import time

import brand
import config
import db
import profiles
import voices
from download import download
from render import render_clip
from transcribe import transcribe

PAD = 4.0


def process_rerender(job):
    p = job.get("payload") or {}
    cid = p.get("clip_id")
    work = config.WORK_DIR / f"re_{cid}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        clip = db.get_clip(cid)
        if not clip:
            raise RuntimeError("El clip ya no existe")
        src = db.get_source(clip["source_id"])
        if src.get("kind") == "live" or not src.get("url"):
            raise RuntimeError("Los clips de directos no se pueden re-renderizar (el directo ya no existe)")
        start, end = float(p["start"]), float(p["end"])
        if not 5 <= end - start <= 180:
            raise RuntimeError("El clip debe durar entre 5 y 180 segundos")
        layout = p.get("layout") or src.get("layout") or config.CLIP_LAYOUT
        # el recuadro manual solo vale para el encuadre con el que se hizo
        custom = src.get("custom_crop") if layout == (src.get("layout") or config.CLIP_LAYOUT) else None

        rf = max(0.0, start - PAD)
        print(f"  Re-render del clip {cid}: {start:.1f}-{end:.1f}s, encuadre {layout}", flush=True)
        video, _title, offset = download(src["url"], work, p.get("quality", "1080p"), str(rf), str(end + PAD))
        _segments, words = transcribe(video, work)
        prof = profiles.get((src.get("options") or {}).get("content_type"))
        if prof.get("voices"):
            voices.label(video, _segments, words)

        out = work / f"{cid}.mp4"
        render_clip(video, words, start - offset, end - offset, out, work, custom_crop=custom, layout=layout,
                    brand=brand.load(work), hook=clip.get("title"),
                    profile=profiles.get((src.get("options") or {}).get("content_type")), opts=src.get("options"))

        path = f"{clip['source_id']}/{cid}_{int(time.time())}.mp4"
        db.upload_clip(path, out)
        in_clip = [{"w": w["w"], "start": w["start"] + offset - start, "end": w["end"] + offset - start}
                   for w in words if start <= w["start"] + offset <= end]
        old = clip.get("storage_path")
        db.update_clip(cid, start_sec=start, end_sec=end, storage_path=path, size_bytes=out.stat().st_size, captions=in_clip)
        if old and old != path:
            db.remove_file(old)
        db.finish_job(job["id"], ok=True)
        print("  Re-render listo", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Re-render falló: {type(e).__name__}: {e}", flush=True)
        db.finish_job(job["id"], ok=False)
    finally:
        shutil.rmtree(work, ignore_errors=True)
