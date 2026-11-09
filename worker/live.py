"""Modo En vivo: graba el directo en trozos, transcribe cada trozo, revisa cada X minutos
y corta clips mientras el directo sigue."""
import shutil
import subprocess
import time
import uuid

import config
import db
from analyze import review_window
from render import render_clip
from transcribe import transcribe


def _duration(path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _resolve(url, quality):
    """Pide a yt-dlp la URL directa del stream. Devuelve (url, título, headers)."""
    import yt_dlp

    # --- ARREGLO YOUTUBE: Forzamos web_safari y un selector de formato flexible ---
    opts = {
        "quiet": True,
        "noplaylist": True,
        "format": "bv*+ba/b",
        "extractor_args": {"youtube": {"player_client": ["web_safari", "default"]}}
    }
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
        
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(url, download=False)
        
    if not info.get("is_live"):
        raise RuntimeError("Ese link no es un directo en vivo (para videos normales usa 'Crear clips')")
        
    stream = info.get("url") or ((info.get("formats") or [{}])[-1].get("url"))
    if not stream:
        raise RuntimeError("No pude obtener el stream del directo")
        
    return stream, info.get("title") or url, info.get("http_headers") or {}


def _start_ffmpeg(stream, headers, seg_dir, logf):
    cmd = ["ffmpeg", "-y", "-loglevel", "warning"]
    if stream.startswith("http"):
        cmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10"]
    if headers and stream.startswith("http"):
        cmd += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in headers.items())]
    cmd += ["-i", stream, "-c", "copy", "-f", "segment", "-segment_time", str(config.SEGMENT_SECONDS),
            "-segment_format", "mpegts", "-reset_timestamps", "1", str(seg_dir / "seg_%05d.ts")]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=logf)


def _stop_ffmpeg(proc):
    if proc.poll() is not None:
        return
    try:
        proc.stdin.write(b"q\n")  # cierre limpio: termina el último trozo
        proc.stdin.flush()
        proc.wait(timeout=20)
    except Exception:  # noqa: BLE001
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def process_live(job):
    sid = job["source_id"]
    src = db.get_source(sid)
    payload = job.get("payload") or {}
    secs = int(payload.get("clip_seconds", 45))
    quality = payload.get("quality", "720p")
    review_sec = int(payload.get("review_minutes", config.REVIEW_MINUTES)) * 60

    work = config.WORK_DIR / sid
    seg_dir = work / "live"
    seg_dir.mkdir(parents=True, exist_ok=True)
    log_path = work / "ffmpeg.log"
    logf = open(log_path, "wb")
    proc = None

    segs = []          # trozos ya transcritos: {path,start,end}
    all_segments = []  # transcripción global (tiempos desde que empezó la grabación)
    all_words = []
    chosen_all = []
    seen_rej = set()
    done = set()
    st = {"offset": 0.0, "last_review": 0.0, "reviews": 0, "clips": 0}
    t0 = time.time()
    stopping = False

    def ingest(f):
        dur = _duration(f)
        if dur < 0.5:
            f.unlink(missing_ok=True)
            return
        start = st["offset"]
        try:
            segments, words = transcribe(f, work)
        except Exception as e:  # noqa: BLE001  (un trozo malo no debe cortar el directo)
            print(f"  aviso: no pude transcribir {f.name}: {e}", flush=True)
            segments, words = [], []
        segments = [{**s, "start": s["start"] + start, "end": s["end"] + start} for s in segments]
        words = [{**w, "start": w["start"] + start, "end": w["end"] + start} for w in words]
        if segments:
            db.save_transcript(sid, segments)
        all_segments.extend(segments)
        all_words.extend(words)
        segs.append({"path": f, "start": start, "end": start + dur})
        st["offset"] = start + dur
        print(f"  trozo {f.name}: {dur:.0f}s, {len(segments)} frases", flush=True)

    def make_clip(m):
        cov = [s for s in segs if s["end"] > m["start"] and s["start"] < m["end"] and s["path"].exists()]
        if not cov:
            return False
        cid = str(uuid.uuid4())
        base = cov[0]["start"]
        lst = work / f"{cid}.txt"
        lst.write_text("".join(f"file '{s['path'].resolve()}'\n" for s in cov))
        win = work / f"{cid}.ts"
        r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(win)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("ffmpeg concat falló: " + r.stderr[-400:])
        wend = cov[-1]["end"]
        end = min(m["end"], wend)
        rel_words = [{**w, "start": w["start"] - base, "end": w["end"] - base}
                     for w in all_words if w["end"] >= base and w["start"] <= wend]
        out = work / f"{cid}.mp4"
        render_clip(win, rel_words, m["start"] - base, end - base, out, work)
        path = f"{sid}/{cid}.mp4"
        db.upload_clip(path, out)
        m["abs_start"], m["abs_end"] = m["start"], end
        in_clip = [{"w": w["w"], "start": w["start"] - m["start"], "end": w["end"] - m["start"]}
                   for w in all_words if m["start"] <= w["start"] <= end]
        db.save_clip(sid, src.get("user_id"), m, path, out.stat().st_size, in_clip)
        for p in (lst, win, out):
            p.unlink(missing_ok=True)
        st["clips"] += 1
        chosen_all.append(m)
        print(f"  clip listo: {m['title']} ({m['score']}%)", flush=True)
        return True

    def review():
        window_from = max(0.0, st["offset"] - 6 * 60)
        win = [s for s in all_segments if s["end"] >= window_from]
        st["last_review"] = st["offset"]
        st["reviews"] += 1
        if not win:
            return
        try:
            new, rej = review_window(win, secs, chosen_all, st["offset"])
            fresh = [r for r in rej if r["title"] not in seen_rej]
            seen_rej.update(r["title"] for r in fresh)
            db.save_rejected(sid, fresh)
            for m in new:
                try:
                    make_clip(m)
                except Exception as e:  # noqa: BLE001
                    print(f"  aviso: no pude crear el clip '{m['title']}': {e}", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  aviso: revisión fallida: {e}", flush=True)
        # libera disco: los clips solo salen de los últimos minutos
        for s in segs:
            if s["end"] < st["offset"] - 20 * 60:
                s["path"].unlink(missing_ok=True)

    try:
        db.set_source(sid, error=None, progress={})
        stream, title, headers = _resolve(src["url"], quality)
        proc = _start_ffmpeg(stream, headers, seg_dir, logf)
        db.set_source(sid, title=title, status="recording")
        print(f"  grabando: {title}", flush=True)

        last_touch = 0.0
        while True:
            db.heartbeat({"live": sid})
            if time.time() - last_touch > 60:
                db.touch_job(job["id"])
                last_touch = time.time()
            if not stopping and db.stop_requested(sid):
                stopping = True
                print("  parada pedida, cerrando…", flush=True)
                _stop_ffmpeg(proc)

            ended = proc.poll() is not None
            files = sorted(seg_dir.glob("seg_*.ts"))
            if ended and not files:
                logf.flush()
                tail = log_path.read_text(errors="ignore")[-500:]
                raise RuntimeError("ffmpeg no pudo grabar el directo: " + tail)
            for f in (files if ended else files[:-1]):
                if f.name not in done:
                    done.add(f.name)
                    ingest(f)

            if st["offset"] - st["last_review"] >= review_sec or (ended and st["offset"] - st["last_review"] >= 20):
                review()

            db.set_progress(sid, recorded_sec=int(time.time() - t0), transcribed_sec=int(st["offset"]),
                            reviews=st["reviews"], clips=st["clips"])
            if ended:
                break
            time.sleep(config.POLL_SECONDS)

        db.set_source(sid, status="stopped" if stopping else "done")
        db.finish_job(job["id"], ok=True)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        db.set_source(sid, status="error", error=str(e)[:500])
        db.finish_job(job["id"], ok=False)
    finally:
        if proc:
            _stop_ffmpeg(proc)
        logf.close()
        shutil.rmtree(work, ignore_errors=True)
