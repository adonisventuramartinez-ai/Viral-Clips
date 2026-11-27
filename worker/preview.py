"""Vista previa antes de renderizar: baja ~6 segundos del video, los pasa por el MISMO render de los clips
(encuadre, gancho, logo, subtítulos, plantilla de marca) y devuelve un cuadro JPG. Así ves cómo va a quedar
sin esperar a que se hagan los 15 clips.
La web crea una fuente temporal + un trabajo 'clip' con payload.preview = true y espera el resultado en sources.progress."""
import shutil
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import brand
import config
import db
import profiles
from download import download
from render import render_clip
from transcribe import transcribe

SPAN = 6.0              # segundos que se renderizan
FRAME_AT = 2.2          # segundo del tramo del que se saca el cuadro (el gancho sigue en pantalla)
HOOK_DEFAULT = "Así se verá tu gancho"


def to_seconds(v, default=60.0) -> float:
    """'1:23', '1:02:03' o '83' -> segundos. Lo que no se entienda cae al valor por defecto."""
    try:
        parts = [float(x) for x in str(v).strip().split(":")]
    except (TypeError, ValueError):
        return default
    if not parts or len(parts) > 3 or any(p < 0 for p in parts):
        return default
    sec = 0.0
    for p in parts:
        sec = sec * 60 + p
    return sec


def extract_frame(video: Path, at: float, out: Path) -> Path:
    """Saca un cuadro JPG del video ya renderizado."""
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{max(0.0, at):.2f}", "-i", str(video),
                        "-frames:v", "1", "-q:v", "3", str(out)], capture_output=True, text=True)
    if r.returncode != 0 or not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError(f"ffmpeg no pudo sacar el cuadro: {r.stderr[-200:]}")
    return out


def make_preview(video: Path, words, start: float, end: float, workdir: Path, out_jpg: Path, *, layout=None,
                 custom_crop=None, brand_cfg=None, hook=None, profile=None, opts=None) -> Path:
    """Renderiza el tramo con la configuración real y devuelve el JPG. `start`/`end` en segundos del archivo `video`."""
    clip = workdir / "preview.mp4"
    try:
        render_clip(video, words, start, end, clip, workdir, custom_crop=custom_crop, layout=layout, brand=brand_cfg,
                    hook=(hook or HOOK_DEFAULT)[:70], profile=profile, opts={**(opts or {}), "tighten": "0", "zoom": "0", "slowmo": "0"})
        return extract_frame(clip, min(FRAME_AT, max(0.5, (end - start) - 0.5)), out_jpg)
    finally:
        clip.unlink(missing_ok=True)


def _cleanup_old(hours=24):
    """Borra de Storage las vistas previas viejas (para no acumular imágenes)."""
    try:
        files = db.sb.storage.from_("uploads").list("preview") or []
        limit = datetime.now(timezone.utc) - timedelta(hours=hours)
        old = []
        for f in files:
            ts = f.get("created_at") or f.get("updated_at")
            if ts and datetime.fromisoformat(str(ts).replace("Z", "+00:00")) < limit:
                old.append(f"preview/{f['name']}")
        if old:
            db.sb.storage.from_("uploads").remove(old)
    except Exception:  # noqa: BLE001
        pass


def process_preview(job):
    p = job.get("payload") or {}
    sid = job["source_id"]
    work = config.WORK_DIR / f"pv_{sid}"
    work.mkdir(parents=True, exist_ok=True)
    try:
        src = db.get_source(sid)
        t0 = to_seconds(p.get("t") if p.get("t") not in (None, "") else src.get("range_from"), 60.0)
        opts = {**(src.get("options") or {}), **{k: v for k, v in p.items() if v is not None}}
        prof = profiles.get(opts.get("content_type"), opts.get("game"))
        layout = src.get("layout") or p.get("layout") or config.CLIP_LAYOUT
        print(f"  Vista previa: {src['url']} en {t0:.0f} s, encuadre {layout}", flush=True)

        video, _title, offset = download(src["url"], work, "720p", str(max(0.0, t0 - 1)), str(t0 + SPAN + 1))
        try:
            _seg, words = transcribe(video, work)
        except Exception as e:  # noqa: BLE001  (sin voz o sin internet: la vista previa sale sin subtítulos)
            print(f"  Vista previa: sin subtítulos ({type(e).__name__}: {str(e)[:80]})", flush=True)
            words = []
        a = max(0.0, t0 - offset)
        jpg = work / "preview.jpg"
        make_preview(video, words, a, a + SPAN, work, jpg, layout=layout, custom_crop=src.get("custom_crop"),
                     brand_cfg=brand.load(work, template=opts.get("brand_template")),
                     hook=str(p.get("hook") or "").strip() or None, profile=prof, opts=opts)

        path = f"preview/{sid}.jpg"
        with open(jpg, "rb") as f:
            db.sb.storage.from_("uploads").upload(path, f.read(), {"content-type": "image/jpeg", "upsert": "true"})
        db.set_progress(sid, preview=path, at=int(time.time()))
        db.finish_job(job["id"], ok=True)
        print("  Vista previa lista", flush=True)
        _cleanup_old()
    except Exception as e:  # noqa: BLE001  (una vista previa no se reintenta: la persona puede pedir otra)
        import jobq
        msg, _r = jobq.explain(e)
        print(f"  Vista previa falló: {type(e).__name__}: {str(e)[:150]}", flush=True)
        try:
            db.set_progress(sid, preview_error=msg)
        except Exception:  # noqa: BLE001
            pass
        db.finish_job(job["id"], ok=False, error=f"{type(e).__name__}: {e}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
