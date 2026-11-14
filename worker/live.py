"""Modo En vivo: graba el directo en trozos, transcribe cada trozo, revisa cada X minutos y corta clips mientras
el directo sigue.

Parte 2:
  - Reconexión automática: si el enlace del stream caduca o se corta, pide uno nuevo y sigue grabando.
  - Pistas en vivo: volumen (🔊), acción en pantalla (🎮, juegos) y chat en vivo de YouTube/Twitch (💬).
  - Tipo de contenido (podcast, entrevista, juego, directo), igual que en Crear clips.
  - Botón "Clip ahora": corta los últimos segundos del directo cuando la web lo pide.
"""
import re
import shutil
import subprocess
import time
import uuid

import brand
import config
import db
import energy
import profiles
import snap
from analyze import review_window, title_for
from livechat import LiveChat
from render import render_clip
from transcribe import transcribe

NOT_LIVE_RECHECK = 10   # segundos entre las dos comprobaciones de "¿ya terminó el directo?"
NOT_LIVE_RE = re.compile(r"not currently live|has ended|is offline|no longer live|stream is offline|is not live|"
                         r"live event will begin|this live event has ended", re.I)


class NotLive(RuntimeError):
    """El link ya no es un directo en vivo (terminó, o nunca lo fue)."""


def _duration(path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _has(f, kind):
    """True si el formato de yt-dlp tiene video ('v') o audio ('a')."""
    c = f.get("vcodec" if kind == "v" else "acodec")
    return c not in (None, "none")


def _resolve(url, quality):
    """Pide a yt-dlp el stream del directo. Devuelve (entradas, mapas_ffmpeg, título). Lanza NotLive si ya terminó."""
    import yt_dlp

    digits = "".join(ch for ch in str(quality) if ch.isdigit())   # "2160p" -> 2160 (4K)
    height = int(digits) if digits else 720
    opts = {"quiet": True, "noplaylist": True,
            "format": f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b/b",
            "remote_components": ["ejs:github"]}
    if config.COOKIES_FILE:
        opts["cookiefile"] = config.COOKIES_FILE
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=False)
    except Exception as e:  # noqa: BLE001
        if NOT_LIVE_RE.search(str(e)):
            raise NotLive("El directo ya terminó") from e
        raise
    if not info.get("is_live"):
        raise NotLive("Ese link no es un directo en vivo (para videos normales usa 'Crear clips')")

    fmts = [f for f in (info.get("requested_formats") or [info]) if f.get("url")]
    if not fmts:
        raise RuntimeError("No pude obtener el stream del directo")
    inputs = [(f["url"], f.get("http_headers") or info.get("http_headers") or {}) for f in fmts]

    if len(fmts) >= 2:
        vi = next((i for i, f in enumerate(fmts) if _has(f, "v")), 0)
        ai = next((i for i, f in enumerate(fmts) if i != vi and _has(f, "a")), 1 - vi if vi < 2 else 1)
        inputs = [inputs[vi], inputs[ai]]
        maps = ["-map", "0:v:0", "-map", "1:a:0?"]
        print("  stream: video y audio por separado (los junto al grabar)", flush=True)
    else:
        maps = ["-map", "0:v:0", "-map", "0:a:0?"]
        if not _has(fmts[0], "a"):
            print("  aviso: YouTube no confirma que este formato traiga audio; reviso al grabar.", flush=True)
    return inputs, maps, info.get("title") or url


def _start_ffmpeg(inputs, maps, seg_dir, logf, session=1):
    """Graba en trozos 's01_seg_00000.ts', 's01_seg_00001.ts'… (el número de sesión sube con cada reconexión)."""
    cmd = ["ffmpeg", "-y", "-loglevel", "warning"]
    for stream, headers in inputs:
        if stream.startswith("http"):
            cmd += ["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "10", "-rw_timeout", "30000000"]
            if headers:
                cmd += ["-headers", "".join(f"{k}: {v}\r\n" for k, v in headers.items())]
        cmd += ["-i", stream]
    cmd += maps + ["-c", "copy", "-f", "segment", "-segment_time", str(config.SEGMENT_SECONDS),
                   "-segment_format", "mpegts", "-reset_timestamps", "1", str(seg_dir / f"s{session:02d}_seg_%05d.ts")]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=logf)


def _has_audio(path) -> bool:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    return "audio" in r.stdout


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


def _fill(d, lo, hi):
    """Lista de valores por segundo de lo a hi a partir de un dict {segundo: valor}; los huecos repiten el valor anterior."""
    out, last = [], None
    for t in range(lo, hi):
        v = d.get(t)
        if v is None:
            v = last
        if v is not None:
            last = v
        out.append(v)
    first = next((v for v in out if v is not None), None)
    return [first if v is None else v for v in out] if first is not None else []


def _clamp(v, default, lo, hi):
    try:
        return max(lo, min(hi, int(float(v))))
    except (TypeError, ValueError):
        return default


def process_live(job):
    sid = job["source_id"]
    src = db.get_source(sid)
    payload = job.get("payload") or {}
    # lo que mandó la web en el trabajo manda sobre lo guardado en la fuente (igual que en Crear clips)
    opts = {**(src.get("options") or {}), **{k: v for k, v in payload.items() if v is not None}}
    prof = profiles.get(opts.get("content_type"))
    game = opts.get("game") or prof.get("game")
    secs = profiles.resolve_secs(payload.get("clip_seconds"), prof)
    quality = payload.get("quality", "720p")
    review_sec = _clamp(payload.get("review_minutes"), config.REVIEW_MINUTES, 1, 10) * 60
    max_new = _clamp(payload.get("max_new"), config.LIVE_MAX_NEW, 1, 10)
    min_score = _clamp(payload.get("min_score"), config.LIVE_MIN_SCORE, 0, 100)
    print(f"  Tipo de contenido: {prof['label']}" + (f" · juego: {game}" if game else "")
          + f" · máx. {max_new} clips por revisión · puntaje mínimo {min_score}", flush=True)

    work = config.WORK_DIR / sid
    seg_dir = work / "live"
    seg_dir.mkdir(parents=True, exist_ok=True)
    log_path = work / "ffmpeg.log"
    logf = open(log_path, "wb")
    proc = None
    chat = None

    segs = []          # trozos ya transcritos: {path,start,end,session}
    all_segments = []  # transcripción global (tiempos desde que empezó la grabación)
    all_words = []
    chosen_all = []
    seen_rej = set()
    done = set()
    lv_audio, lv_scene = {}, {}      # volumen (dB) y cambio de imagen por segundo de la grabación
    waiting = {}                     # pedidos de "Clip ahora" esperando el próximo trozo: id -> {offset, since, secs}
    st = {"offset": 0.0, "last_review": 0.0, "reviews": 0, "clips": 0, "reconnects": 0, "session": 1, "state": "recording"}
    t0 = time.time()
    stopping = False

    # ------------------------------------------------------------------ trozos
    def ingest(f):
        sess = int(re.match(r"s(\d+)_", f.name).group(1)) if re.match(r"s(\d+)_", f.name) else 1
        dur = _duration(f)
        if dur < 0.5:
            f.unlink(missing_ok=True)
            return
        start = st["offset"]
        try:
            if not _has_audio(f):
                if not st.get("warned_mute"):
                    print("  ✗ Este trozo NO trae audio: no hay nada que transcribir. Mira ffmpeg.log / avísame.", flush=True)
                    st["warned_mute"] = True
                raise RuntimeError("trozo sin audio")
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
        # pistas del trozo: volumen y (si el tipo de contenido lo usa) cambios de imagen
        try:
            base = int(start)
            for i, v in enumerate(energy.audio_levels(f)):
                lv_audio[base + i] = v
            if prof["bonus"].get("motion"):
                for i, v in enumerate(energy.scene_levels(f)):
                    lv_scene[base + i] = v
        except Exception as e:  # noqa: BLE001  (las pistas son un extra)
            print(f"  aviso: no pude calcular pistas de {f.name} ({type(e).__name__})", flush=True)
        segs.append({"path": f, "start": start, "end": start + dur, "session": sess})
        st["offset"] = start + dur
        print(f"  trozo {f.name}: {dur:.0f}s, {len(segments)} frases", flush=True)

    def signals(lo, hi):
        """(volumen, acción, chat) como conjuntos de segundos absolutos dentro de [lo, hi)."""
        loud = {lo + i for i in energy.loud_from_levels(_fill(lv_audio, lo, hi))}
        motion = ({lo + i for i in energy.motion_from_levels(_fill(lv_scene, lo, hi))}
                  if prof["bonus"].get("motion") else set())
        hot_chat = set()
        if chat and config.LIVE_CHAT:
            try:
                hot_chat = chat.hot(lo, hi)
            except Exception:  # noqa: BLE001
                hot_chat = set()
        return loud, motion, hot_chat

    # ------------------------------------------------------------------ clips
    def make_clip(m):
        """Corta el momento m (tiempos de la grabación). Devuelve el id del clip, o None si no hay video de ese tramo."""
        cov = [s for s in segs if s["end"] > m["start"] and s["start"] < m["end"] and s["path"].exists()]
        if cov:
            # si el tramo cruza una reconexión, se queda solo con la última parte seguida (no se pueden pegar dos sesiones)
            last = cov[-1]["session"]
            cov = [s for s in cov if s["session"] == last]
        if not cov:
            return None
        cid = str(uuid.uuid4())
        base = cov[0]["start"]
        lst = work / f"{cid}.txt"
        lst.write_text("".join(f"file '{s['path'].resolve()}'\n" for s in cov))

        # Unimos los .ts y lo convertimos a .mp4 estándar
        win_ts = work / f"{cid}.ts"
        r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(win_ts)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("ffmpeg concat falló: " + r.stderr[-400:])
        win = work / f"{cid}_clean.mp4"
        r2 = subprocess.run(["ffmpeg", "-y", "-i", str(win_ts), "-c", "copy", str(win)], capture_output=True, text=True)
        if r2.returncode != 0:
            raise RuntimeError("ffmpeg conversion a mp4 falló: " + r2.stderr[-400:])

        wend = cov[-1]["end"]
        mstart = max(m["start"], base)
        end = min(m["end"], wend)
        rel_words = [{**w, "start": w["start"] - base, "end": w["end"] - base}
                     for w in all_words if w["end"] >= base and w["start"] <= wend]

        out = work / f"{cid}.mp4"
        render_clip(win, rel_words, mstart - base, end - base, out, work,
                    custom_crop=src.get("custom_crop"), layout=src.get("layout"), brand=st.get("brand"),
                    hook=m.get("hook") or m["title"])
        path = f"{sid}/{cid}.mp4"
        db.upload_clip(path, out)
        m["abs_start"], m["abs_end"] = mstart, end
        in_clip = [{"w": w["w"], "start": w["start"] - mstart, "end": w["end"] - mstart}
                   for w in all_words if mstart <= w["start"] <= end]
        db.save_clip(sid, src.get("user_id"), m, path, out.stat().st_size, in_clip)

        for p in (lst, win_ts, win, out):   # borramos todos los temporales
            p.unlink(missing_ok=True)
        st["clips"] += 1
        chosen_all.append(m)
        print(f"  clip listo: {m['title']} ({m['score']}%)", flush=True)
        return cid

    def review():
        window_from = max(0.0, st["offset"] - 6 * 60)
        win = [s for s in all_segments if s["end"] >= window_from]
        st["last_review"] = st["offset"]
        st["reviews"] += 1
        if not win:
            return
        try:
            lo, hi = int(window_from), int(st["offset"])
            loud, motion, hot_chat = signals(lo, hi)
            n_hot = energy.annotate(win, loud, hot_chat, motion)
            ai_win = energy.add_action_markers(win, loud, motion, hot_chat) if prof.get("action") else win
            print(f"  Pistas: {len(loud)} s de volumen alto, {len(motion)} s de acción, {len(hot_chat)} s de chat, "
                  f"{n_hot} frase(s) marcada(s)", flush=True)
            words_win = [w for w in all_words if w["end"] >= window_from]
            new, rej = review_window(ai_win, secs, chosen_all, st["offset"], min_score=min_score, max_new=max_new,
                                     words=words_win, profile=prof, game=game)
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

    # ------------------------------------------------------------------ "Clip ahora"
    def serve_clip_now(c, info):
        end = st["offset"]
        n = _clamp(info["secs"], secs, 15, 120)
        start = max(0.0, end - n)
        text = " ".join(s["text"] for s in all_segments if s["end"] > start and s["start"] < end)
        words_win = [w for w in all_words if w["end"] >= start - 6 and w["start"] <= end]
        if words_win:       # que no arranque a media palabra: sube al inicio de la frase más cercano
            start = max(0.0, snap.snap_start(start, words_win))
        meta = title_for(text, fallback="Clip del directo")
        m = {"start": start, "end": end, "score": 70, "title": meta["title"], "hook": meta["hook"],
             "description": meta["description"], "hashtags": meta["hashtags"],
             "reason": "Clip manual (botón Clip ahora)"}
        cid = make_clip(m)
        if cid:
            db.finish_command(c["id"], True, "Listo", cid)
        else:
            db.finish_command(c["id"], False, "Ese tramo ya no está en el disco")

    def handle_commands(force=False):
        for c in db.pending_commands(sid):
            if c["id"] not in waiting:
                waiting[c["id"]] = {"offset": st["offset"], "since": time.time(), "secs": c.get("seconds") or secs, "cmd": c}
        for cid_, info in list(waiting.items()):
            c = info["cmd"]
            new_chunk = st["offset"] > info["offset"] + 0.5
            late = time.time() - info["since"] > config.SEGMENT_SECONDS * 3 + 90
            if not (new_chunk or force or late):
                continue
            waiting.pop(cid_, None)
            if st["offset"] < 5:
                db.finish_command(c["id"], False, "Todavía no hay video grabado")
                continue
            try:
                serve_clip_now(c, info)
            except Exception as e:  # noqa: BLE001
                print(f"  aviso: 'Clip ahora' falló: {e}", flush=True)
                db.finish_command(c["id"], False, f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------------ reconexión
    def reconnect():
        """Pide un enlace nuevo del directo y vuelve a grabar. Devuelve 'ok', 'ended', 'stop' o 'failed'."""
        nonlocal proc
        not_live = 0
        for attempt in range(config.LIVE_RECONNECTS):
            if db.stop_requested(sid):
                return "stop"
            st["state"] = "reconnecting"
            try:
                inputs, maps, _t = _resolve(src["url"], quality)
                st["session"] += 1
                proc = _start_ffmpeg(inputs, maps, seg_dir, logf, st["session"])
                if chat:
                    chat.session_start(st["offset"])
                st["reconnects"] += 1
                st["state"] = "recording"
                print(f"  ↻ reconectado (sesión {st['session']}, intento {attempt + 1})", flush=True)
                return "ok"
            except NotLive:
                not_live += 1
                if not_live >= 2:       # dos veces seguidas "ya no está en vivo": terminó de verdad
                    return "ended"
                wait = NOT_LIVE_RECHECK
            except Exception as e:  # noqa: BLE001
                wait = min(60, 5 * 2 ** attempt)
                print(f"  reconexión {attempt + 1}/{config.LIVE_RECONNECTS} falló ({type(e).__name__}: {str(e)[:100]}); "
                      f"pruebo otra vez en {wait} s", flush=True)
            end_wait = time.time() + wait
            while time.time() < end_wait:
                db.heartbeat({"live": sid})
                time.sleep(1)
        return "failed"

    # ------------------------------------------------------------------ bucle principal
    try:
        db.set_source(sid, error=None, progress={})
        st["brand"] = brand.load(work)
        st["brand"]["progress_bar"] = bool(opts.get("progress_bar"))
        inputs, maps, title = _resolve(src["url"], quality)
        proc = _start_ffmpeg(inputs, maps, seg_dir, logf, st["session"])
        db.set_source(sid, title=title, status="recording")
        print(f"  grabando: {title}", flush=True)
        if config.LIVE_CHAT:
            chat = LiveChat(src["url"])
            chat.session_start(0.0)
            chat.start()

        last_touch = 0.0
        last_new_file = time.time()
        n_files = 0
        fails = 0
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
            files = sorted(seg_dir.glob("s*_seg_*.ts"))
            prefix = f"s{st['session']:02d}_"
            cur = [f for f in files if f.name.startswith(prefix)]
            writing = cur[-1] if (cur and not ended) else None      # el trozo que ffmpeg todavía está escribiendo
            for f in files:
                if f.name not in done and f != writing:
                    done.add(f.name)
                    ingest(f)
            if len(files) > n_files:
                n_files, last_new_file = len(files), time.time()

            # si ffmpeg sigue vivo pero no sale ningún trozo nuevo, el stream se congeló: se mata para reconectar
            if not ended and not stopping and time.time() - last_new_file > config.SEGMENT_SECONDS * 3 + 60:
                print("  el stream se congeló (sin trozos nuevos), reconecto…", flush=True)
                proc.terminate()
                last_new_file = time.time()

            final = False
            if ended:
                if chat:
                    chat.session_end()
                if stopping:
                    final = True
                else:
                    fails = 0 if cur else fails + 1
                    tail = ""
                    try:
                        logf.flush()
                        tail = log_path.read_text(errors="ignore")[-300:].strip()
                    except Exception:  # noqa: BLE001
                        pass
                    print(f"  ffmpeg se detuvo ({'con' if cur else 'sin'} video nuevo)" + (f": {tail}" if tail else ""), flush=True)
                    res = reconnect() if fails <= config.LIVE_RECONNECTS else "failed"
                    if res == "ok":
                        last_new_file = time.time()
                        n_files = len(list(seg_dir.glob("s*_seg_*.ts")))
                    elif res == "failed" and st["offset"] < 1:
                        raise RuntimeError("ffmpeg no pudo grabar el directo: " + tail)
                    else:
                        final = True        # ended / stop / failed (pero ya había grabado algo)
                        stopping = stopping or res == "stop"

            if st["offset"] - st["last_review"] >= review_sec or (final and st["offset"] - st["last_review"] >= 20):
                review()
            handle_commands(force=final)

            db.set_progress(sid, recorded_sec=int(time.time() - t0), transcribed_sec=int(st["offset"]),
                            reviews=st["reviews"], clips=st["clips"], reconnects=st["reconnects"], state=st["state"],
                            chat_msgs=(chat.count() if chat else 0), pending_now=len(waiting))
            if final:
                break
            time.sleep(config.POLL_SECONDS)

        db.set_source(sid, status="stopped" if stopping else "done")
        db.finish_job(job["id"], ok=True)
    except NotLive as e:
        # el link nunca fue un directo en vivo: se avisa claro y no se reintenta
        db.set_source(sid, status="error", error=str(e)[:500])
        db.finish_job(job["id"], ok=False)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        db.set_source(sid, status="error", error=str(e)[:500])
        db.finish_job(job["id"], ok=False)
    finally:
        for cmd_id, info in list(waiting.items()):      # pedidos que quedaron sin atender
            db.finish_command(info["cmd"]["id"], False, "El directo terminó antes de poder cortar")
        if chat:
            chat.stop()
        if proc:
            _stop_ffmpeg(proc)
        logf.close()
        shutil.rmtree(work, ignore_errors=True)
