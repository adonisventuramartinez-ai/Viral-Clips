"""Estudio de "Hacerlo viral": atiende lo que pides desde la web sobre un clip (rehacer miniaturas, volver a analizar)
y les pone miniatura a los clips que llegaron sin ella (en vivo, rehechos).

La web deja un pedido en clips.viral_req = {"action": "thumbs"|"reanalyze", "a": {text,time,style}, "b": {...}}.
El worker lo toma, lo hace y lo borra. Si falla deja {"error": "motivo"} para que la web lo muestre.
Corre en su propio hilo (start_thread): una miniatura no espera a que termine un render ni un directo.
"""
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import config
import thumb

ACTIONS = ("thumbs", "reanalyze")
SLOTS = {"a": "thumb_path", "b": "thumb_b_path"}


# ----------------------------------------------------------------------------- lógica pura
def clean_req(req):
    """Valida el pedido que dejó la web. Devuelve {action, slots:{a:{text,time,style}}} limpio, o None si no sirve."""
    if not isinstance(req, dict) or req.get("action") not in ACTIONS or req.get("error"):
        return None
    out = {"action": req["action"], "slots": {}, "auto": bool(req.get("auto"))}
    if req["action"] == "thumbs":
        for slot in SLOTS:
            a = req.get(slot)
            if not isinstance(a, dict):
                continue
            text = " ".join(str(a.get("text") or "").split())[:40]
            try:
                t = float(a["time"]) if a.get("time") is not None else None
                t = t if t is not None and 0 <= t <= 600 else None
            except (TypeError, ValueError):
                t = None
            style = str(a.get("style") or "").lower()
            out["slots"][slot] = {"text": text, "time": t, "style": style if style in thumb.STYLES else ""}
        if not out["slots"]:
            return None
    return out


def default_text(v, slot, title=""):
    """Texto de la miniatura cuando nadie lo escribió: el de la IA (el 2.º para la B) o el título."""
    v = v or {}
    tt = v.get("thumb_texts") or []
    if slot == "b" and len(tt) > 1:
        return tt[1]
    return v.get("thumb_text") or (tt[0] if tt else "") or " ".join(str(title or "Clip").split()[:4])


def new_thumb_path(source_id, clip_id, slot, now=None):
    """Ruta NUEVA cada vez (con la hora): así el navegador y las redes nunca ven la miniatura vieja en caché."""
    return f"thumbs/{source_id or 'x'}/{clip_id}_{slot}_{int(now if now is not None else time.time())}.jpg"


# ----------------------------------------------------------------------------- acciones
def make_thumbs(clip, slots, db, workdir):
    """Rehace las miniaturas pedidas bajando el clip ya terminado. Devuelve (campos para guardar, rutas viejas a borrar)."""
    path = clip.get("storage_path")
    if not path:
        raise RuntimeError("el clip no tiene archivo")
    v = dict(clip.get("viral") or {})
    info = {k: dict(x) for k, x in (v.get("thumb") or {}).items() if isinstance(x, dict)}
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    f = workdir / f"{clip['id']}.mp4"
    f.write_bytes(db.download_clip(path))
    fields, old = {}, []
    for slot, a in slots.items():
        prev = info.get(slot) or {}
        text = a.get("text") or prev.get("text") or default_text(v, slot, clip.get("title"))
        style = a.get("style") or prev.get("style") or thumb.DEFAULT_STYLE
        at = a.get("time") if a.get("time") is not None else prev.get("time")   # solo cambió el texto: se queda en el mismo cuadro
        out = workdir / f"{clip['id']}_{slot}.jpg"
        jpg, used = thumb.make_t(f, text, out, rank=0 if slot == "a" else 1, at=at, style=style)
        if not jpg:
            raise RuntimeError("no pude sacar ese cuadro del video")
        if jpg.stat().st_size > config.THUMB_MAX_BYTES:
            raise RuntimeError("la miniatura quedó muy pesada")
        newp = new_thumb_path(clip.get("source_id"), clip["id"], slot)
        db.upload_thumb(newp, jpg)
        jpg.unlink(missing_ok=True)
        col = SLOTS[slot]
        if clip.get(col) and clip[col] != newp:
            old.append(clip[col])
        fields[col] = newp
        info[slot] = {"text": text, "style": style, "time": used}
    v["thumb"] = info
    if "a" in info:
        v["thumb_text"] = info["a"]["text"]
    v.pop("thumb_tried", None)
    fields["viral"] = v
    return fields, old


def reanalyze(clip):
    """Vuelve a pedirle a la IA títulos, hashtags y puntaje. NO cambia tu título ni tus hashtags: solo renueva las sugerencias.
    Si ya lo aprobaste, sigue aprobado. Devuelve los campos para guardar."""
    import viral
    caps = " ".join(str(c.get("w", "")) for c in (clip.get("captions") or []) if isinstance(c, dict))
    dur = float(clip.get("end_sec") or 0) - float(clip.get("start_sec") or 0)
    old = clip.get("viral") or {}
    v = viral.run({"title": clip.get("title"), "score": clip.get("viral_score"), "hashtags": clip.get("hashtags")}, caps, None, dur or None)
    if old.get("thumb"):
        v["thumb"] = old["thumb"]
    v["title_original"] = old.get("title_original") or v.get("title_original")
    fields = {"viral": v}
    if clip.get("viral_status") != "approved":
        fields["viral_status"] = viral.status_for(v)
    return fields


def handle(row, db, workdir=None):
    """Atiende el pedido de un clip. Devuelve True si salió bien."""
    cid = row["id"]
    req = clean_req(row.get("viral_req"))
    if not req:
        db.update_clip(cid, viral_req=None)
        return False
    work = Path(workdir or config.WORK_DIR / "studio") / cid
    try:
        if req["action"] == "reanalyze":
            fields, old = reanalyze(row), []
        else:
            fields, old = make_thumbs(row, req["slots"], db, work)
        db.update_clip(cid, viral_req=None, **fields)
        for p in old:
            db.remove_file(p)
        print(f"  Estudio viral: {req['action']} listo para «{row.get('title')}»", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        msg = f"{type(e).__name__}: {str(e)[:160]}" if not isinstance(e, RuntimeError) else str(e)[:200]
        print(f"  Estudio viral: no pude ({msg})", flush=True)
        try:
            db.update_clip(cid, viral_req={"error": msg, "at": datetime.now(timezone.utc).isoformat()})
        except Exception:  # noqa: BLE001
            pass
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


def backfill(row, db, workdir=None):
    """Miniatura automática para un clip que llegó sin ella. Si falla, se marca para no reintentarlo cada vuelta."""
    v = row.get("viral") or {}
    slots = {"a": {}}
    if config.VIRAL_THUMB_AB and not row.get("thumb_b_path"):
        slots["b"] = {}
    work = Path(workdir or config.WORK_DIR / "studio") / row["id"]
    try:
        fields, _old = make_thumbs(row, slots, db, work)
        db.update_clip(row["id"], **fields)
        print(f"  Estudio viral: miniatura hecha para «{row.get('title')}»", flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"  Estudio viral: no pude hacer la miniatura de «{row.get('title')}» ({str(e)[:100]})", flush=True)
        try:
            db.update_clip(row["id"], viral={**v, "thumb_tried": True})
        except Exception:  # noqa: BLE001
            pass
        return False
    finally:
        shutil.rmtree(work, ignore_errors=True)


def tick(db=None, workdir=None):
    """Una vuelta: atiende pedidos de la web y hace miniaturas que faltan. Devuelve cuántas cosas hizo."""
    if db is None:
        import db as db
    n = 0
    for row in db.clips_with_requests(3):
        n += 1 if handle(row, db, workdir) else 0
    if config.THUMBS and config.VIRAL:
        for row in db.clips_missing_thumbs(config.THUMB_BACKFILL_PER_TICK):
            n += 1 if backfill(row, db, workdir) else 0
    return n


def _loop():
    while True:
        try:
            tick()
        except Exception as e:  # noqa: BLE001  (el estudio es un extra: nunca debe tumbar nada)
            print(f"Estudio viral: error ({type(e).__name__}: {str(e)[:100]})", flush=True)
        time.sleep(config.STUDIO_SECONDS)


def start_thread():
    t = threading.Thread(target=_loop, name="studio", daemon=True)
    t.start()
    return t
