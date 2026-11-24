"""Worker de ClipForge: toma jobs 'download' (videos) y 'record' (directos) y produce clips verticales."""
import re
import shutil
import subprocess
import time
import traceback
import urllib.request
import uuid
from pathlib import Path

import config
import db
import detect
import discover
from analyze import find_moments
from download import download, parse_ts
import live
import rerender
import selfcheck
import watcher
import brand
import energy
import hook as hooks
import jobq
import render
import lifecycle
import logx
import voices
import profiles
import original
import ai_video
import publisher
import autoqueue
import poster
import scheduler
import packager
import thumb
import studio
import viral
from render import render_clip
from transcribe import transcribe


class Cancelled(Exception):
    """La fuente se quitó desde la web (botón Limpiar) mientras se procesaba."""


def detect_signals(video, prof, words, levels, chat=None, lo=0):
    """Detectores extra de la Parte 3 según el tipo de contenido. Devuelve ({marca: segundos}, {segundo: 'WASTED'}).
    Cada uno es opcional: si falla o está apagado en .env (DETECT_AUDIO / DETECT_SCREEN / DETECT_ARGUMENT) se omite."""
    sig = prof.get("signals") or {}
    extra, labels = {}, {}
    if sig.get("combat") and config.DETECT_AUDIO:
        shots, booms = detect.combat_seconds(video)
        if shots or booms:
            extra[profiles.EXTRA_MARK["combat"]] = shots | booms
        print(f"  Audio: {len(shots)} s de tiroteo, {len(booms)} s con explosión", flush=True)
    if sig.get("screen") and config.DETECT_SCREEN:
        ev = detect.screen_events(video)
        if ev:
            extra[profiles.EXTRA_MARK["screen"]] = set(ev)
            labels = {t: detect.SCREEN_MARK[k] for t, k in ev.items()}
        print(f"  Pantalla: {len(ev)} s con WASTED/BUSTED/MISSION PASSED/estrellas", flush=True)
    if sig.get("argument") and config.DETECT_ARGUMENT:
        arg = detect.argument_seconds(words, levels, chat, lo=lo)
        if arg:
            extra[profiles.EXTRA_MARK["argument"]] = arg
        print(f"  Discusiones: {len(arg)} s con pelea o discusión", flush=True)
    return extra, labels


# ------------------------------------------------------------------- Modo Transformar
def _probe_duration(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0.0


def _check_transform_size(path, label="video"):
    """Falla temprano si el archivo de entrada supera TRANSFORM_MAX_MB (aunque venga de un link)."""
    mb = Path(path).stat().st_size / 1024 / 1024
    if mb > config.TRANSFORM_MAX_MB:
        raise RuntimeError(
            f"El {label} pesa {mb:.1f} MB y el tope es {config.TRANSFORM_MAX_MB:g} MB. "
            "Comprime el video o usa un link más corto."
        )
    return Path(path)


def _fetch_transform_source(src, payload, work):
    """Consigue el video: primero el archivo subido a Storage; si no, un link directo o cualquier URL soportada por yt-dlp."""
    up = payload.get("upload_path") or src.get("storage_path")
    if up:
        dest = work / ("input" + (Path(str(up)).suffix.lower() or ".mp4"))
        print(f"  Transformar: bajo el video subido ({up})", flush=True)
        return _check_transform_size(db.download_input(up, dest), "archivo subido")

    url = str(src.get("url") or "").strip()
    if not url:
        raise RuntimeError("Falta el video para transformar")
    # Link directo a un archivo (o URL firmada de Supabase): descarga simple, sin yt-dlp.
    if re.search(r"\.(mp4|m4v|mov|webm|mkv|avi)(\?|$)", url, re.I):
        dest = work / "input.mp4"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ClipForge)"})
        limit = int(config.TRANSFORM_MAX_MB * 1024 * 1024)
        print("  Transformar: descargando link directo…", flush=True)
        total = 0
        with urllib.request.urlopen(req, timeout=180) as resp, open(dest, "wb") as f:
            declared = resp.headers.get("Content-Length") or ""
            if declared.isdigit() and int(declared) > limit:
                raise RuntimeError(f"El link directo anuncia {int(declared) / 1048576:.1f} MB y el tope es {config.TRANSFORM_MAX_MB:g} MB.")
            while True:  # streaming con tope: nunca descargamos un archivo descomunal
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise RuntimeError(f"El link directo supera los {config.TRANSFORM_MAX_MB:g} MB; aborto la descarga.")
                f.write(chunk)
        if dest.stat().st_size < 1024:
            raise RuntimeError("El link directo devolvió un archivo vacío")
        return _check_transform_size(dest, "link directo")
    # YouTube y demás: se reutiliza el descargador de siempre.
    video, _title, _offset = download(url, work, payload.get("quality", "1080p"),
                                      src.get("range_from"), src.get("range_to"))
    return _check_transform_size(video, "video descargado")


def _normalize_transform(video, work, opts):
    """Fuerza 1080x1920 sin distorsión, con logo y audio garantizado. Duración y bitrate acotados."""
    out = work / "transform_normalized.mp4"
    dur = _probe_duration(video)
    ss = parse_ts(opts.get("range_from")) or 0.0
    to = parse_ts(opts.get("range_to")) or 0.0
    max_sec = config.TRANSFORM_MAX_SECONDS
    end = min(to or (ss + max_sec), ss + max_sec, dur or (ss + max_sec))
    if end <= ss + 0.5:
        end = ss + min(dur or max_sec, max_sec)
    length = max(1.0, end - ss)
    if dur and dur > length + 1:
        print(f"  Transformar: video de {int(dur)} s → uso {int(length)} s para no saturar el worker", flush=True)

    vf = (f"scale={original.W}:{original.H}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={original.W}:{original.H},setsar=1,fps={original.FPS}")
    cap = original.size_cap(length)   # tope para que el MP4 final nunca pase de CLIP_MAX_MB
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{ss:.2f}", "-t", f"{length:.2f}", "-i", str(video)]

    logo_cfg = brand.load(work, template=opts.get("brand_template"))
    logo = Path(logo_cfg["path"]) if logo_cfg.get("path") else None
    has_logo = bool(logo and logo.exists())
    if has_logo:
        cmd += ["-i", str(logo)]      # render._logo_graph espera el logo en el input [1:v]

    probe_a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                              "-of", "csv=p=0", str(video)], capture_output=True, text=True)
    has_audio = bool(probe_a.stdout.strip())
    audio_idx = 0
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_idx = 2 if has_logo else 1

    if has_logo:
        graph = render._logo_graph(f"[0:v]{vf}[v]", logo_cfg, "v")
        cmd += ["-filter_complex", graph, "-map", "[out]", "-map", f"{audio_idx}:a:0"]
    else:
        cmd += ["-vf", vf, "-map", "0:v:0", "-map", f"{audio_idx}:a:0"]
    cmd += ["-c:v", "libx264", "-preset", config.CLIP_PRESET, "-crf", str(config.CLIP_CRF),
            "-maxrate", str(cap), "-bufsize", str(cap * 2), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]

    r = subprocess.run(cmd, cwd=work, capture_output=True, text=True, timeout=max(300, int(length * 4)))
    if r.returncode != 0 or not out.exists():
        raise RuntimeError("No pude normalizar el video: " + (r.stderr or "")[-400:])
    return out


def process_transform(job):
    """Video externo → clip vertical con Modo Original: voz, contexto, dramómetro, encuesta y marca."""
    sid = job["source_id"]
    src = db.get_source(sid) or {}
    payload = job.get("payload") or {}
    opts = {**(src.get("options") or {}), **{k: v for k, v in payload.items() if v is not None}}
    work = config.WORK_DIR / sid
    work.mkdir(parents=True, exist_ok=True)
    st = logx.Stages()

    def alive():
        if not db.source_exists(sid):
            raise Cancelled()

    try:
        if int(job.get("attempts") or 1) > 1:
            n = db.reset_source_outputs(sid)
            print(f"  Reintento: limpié {n} clip(s) a medias del intento anterior", flush=True)

        st.begin("descarga")
        db.set_source(sid, status="downloading", error=None)
        video = _fetch_transform_source(src, payload, work)
        alive()

        st.begin("normalización")
        db.set_source(sid, status="transcribing")
        norm = _normalize_transform(video, work, opts)
        if video != norm:
            video.unlink(missing_ok=True)

        st.begin("transcripción")
        try:
            segs, words = transcribe(norm, work)
        except Exception as e:  # noqa: BLE001  (sin texto igual podemos narrar el contexto genérico)
            print(f"  Transcripción: no pude ({type(e).__name__}: {str(e)[:120]}); uso el título como contexto.", flush=True)
            segs, words = [], []
        if segs:
            db.save_transcript(sid, segs)
        text = " ".join(s["text"] for s in segs).strip()[:2500] or str(payload.get("title") or src.get("title") or "")
        alive()

        st.begin("modo original")
        ocfg = original.load(work, content_type=str(opts.get("content_type") or "podcast"))
        want = payload.get("original")
        if want is not None:
            ocfg["enabled"] = str(want).lower() not in ("0", "false", "no", "off")
        if config.TRANSFORM_ALWAYS_ORIGINAL:
            ocfg["enabled"] = True
        # Anti-penalización: voz y tarjetas propias desde el primer segundo.
        ocfg["intro"] = config.TRANSFORM_INTRO
        ocfg["narrate"] = True
        ocfg["meter"] = True
        ocfg["poll"] = True
        ex = original.extras(text, ocfg)

        cid = str(uuid.uuid4())
        out = work / f"{cid}.mp4"
        try:
            score = int(payload.get("score") or config.TRANSFORM_DEFAULT_SCORE)
        except (TypeError, ValueError):
            score = config.TRANSFORM_DEFAULT_SCORE
        try:
            original.wrap_clip(norm, ex, out, work, ocfg, score=score)
        except Exception as e:  # noqa: BLE001  (si falla la envoltura, se sube el video normalizado)
            print(f"  Modo Original: no pude envolver ({type(e).__name__}: {str(e)[:140]}); subo el video normalizado.", flush=True)
            shutil.copy(norm, out)

        base = {
            "title": (payload.get("title") or src.get("title") or f"{ocfg['show']} · clip transformado")[:100],
            "score": score,
            "reason": "Video externo transformado con aporte propio: narración, contexto, dramómetro y encuesta.",
            "abs_start": 0.0,
            "abs_end": _probe_duration(out),
        }
        m = {**base, "description": original.description(base, ex, ocfg)}
        path = f"{sid}/{cid}.mp4"
        db.upload_clip(path, out)
        sync = config.SUB_SYNC_OFFSET
        words = [{**w, "start": w["start"] + sync, "end": w["end"] + sync} for w in words]
        db.save_clip(sid, src.get("user_id"), m, path, out.stat().st_size, words)
        db.set_source(sid, status="done", title=base["title"])
        db.finish_job(job["id"], ok=True)
        print(f"Transformación lista: {base['title']} ({base['abs_end']:.0f} s) · {st.summary()}", flush=True)
    except Cancelled:
        print(f"  fuente {sid} quitada desde la web, cancelo.", flush=True)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        fail(job, e, source_id=sid)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def process(job):
    sid = job["source_id"]
    src = db.get_source(sid)
    payload = job.get("payload") or {}
    n_clips = int(payload.get("clips", 15))
    quality = payload.get("quality", "1080p")
    # Opciones de contenido: lo que mandó la web en el trabajo manda sobre lo guardado en la fuente
    opts = {**(src.get("options") or {}), **{k: v for k, v in payload.items() if v is not None}}
    prof = profiles.get(opts.get("content_type"), opts.get("game"))
    game = opts.get("game") or prof.get("game")
    secs = profiles.resolve_secs(payload.get("clip_seconds"), prof)
    print(f"  Tipo de contenido: {prof['label']}" + (f" · juego: {game}" if game else "") + f" · clips de ~{secs} s", flush=True)

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
    st = logx.Stages()
    try:
        if int(job.get("attempts") or 1) > 1:   # reintento: limpiar lo que dejó el intento anterior
            n = db.reset_source_outputs(sid)
            print(f"  Reintento: limpié {n} clip(s) a medias del intento anterior", flush=True)
        st.begin("descarga")
        db.set_source(sid, status="downloading", error=None)
        video, title, offset = download(src["url"], work, quality, src.get("range_from"), src.get("range_to"))
        alive()
        db.set_source(sid, title=title, status="transcribing")
        st.begin("transcripción")

        segments, words = transcribe(video, work)
        if not segments:
            raise RuntimeError("No se detectó voz en el video")
        
        db.save_transcript(sid, [{**s, "start": s["start"] + offset, "end": s["end"] + offset} for s in segments])
        if prof.get("voices"):   # Parte 5: quién habla (P1, P2...) para la IA, las discusiones y los colores de subtítulos
            n_voices = voices.label(video, segments, words)
            print(f"  Voces: {n_voices} persona(s) distintas" if n_voices >= 2 else "  Voces: no distingo más de una (sigo sin etiquetas)", flush=True)

        alive()
        st.begin("análisis")
        db.set_source(sid, status="analyzing")
        ai_segments = segments
        try:
            dur_v = segments[-1]["end"]
            levels = energy.audio_levels(video)
            loud = energy.loud_from_levels(levels)
            motion = energy.motion_seconds(video) if prof["bonus"].get("motion") else set()
            chat = energy.chat_seconds(src["url"], work, offset, dur_v)
            extra, labels = detect_signals(video, prof, words, levels, chat)
            n_hot = energy.annotate(segments, loud, chat, motion, extra=extra, labels=labels)
            print(f"  Pistas: {len(loud)} s con volumen alto, {len(motion)} s de acción en pantalla, {n_hot} frase(s) marcada(s)", flush=True)
            if prof.get("action"):
                ai_segments = energy.add_action_markers(segments, loud, motion, chat, extra=extra, labels=labels)
        except Exception as e:  # noqa: BLE001  (las pistas son un extra: nunca deben tumbar el trabajo)
            print(f"  Pistas: no pude calcularlas ({type(e).__name__}: {e})", flush=True)
        known = db.recent_clip_texts(src.get("user_id"), config.DEDUPE_HOURS) if (prof.get("dedupe") and config.DEDUPE) else []
        chosen, rejected = find_moments(ai_segments, n_clips, secs, words=words, profile=prof, game=game,
                                        video=video, known_texts=known)
        db.save_rejected(sid, rejected)
        if not chosen:
            raise RuntimeError("La IA no encontró momentos para clips")

        st.begin("clips")
        db.set_source(sid, status="clipping")
        logo = brand.load(work, template=opts.get("brand_template"))
        logo["progress_bar"] = bool(opts.get("progress_bar"))
        ocfg = original.load(work)
        made, published = [], 0
        for m in sorted(chosen, key=lambda x: x["start"]):
            alive()
            cid = str(uuid.uuid4())
            out = work / f"{cid}.mp4"

            if config.SMART_START and ocfg.get("smart_start", True):
                try:   # que el clip entre en la primera frase fuerte y que el texto de arriba diga algo concreto (la gente decide en 2 s)
                    new_start, note = hooks.refine_start(words, m["start"], m["end"])
                    if note:
                        print(f"  Gancho: {note}", flush=True)
                        m["start"] = new_start
                    m["hook"] = hooks.best_hook(m.get("hook"), m["title"], words, m["start"], m["end"])
                except Exception as e:  # noqa: BLE001  (es un extra: si falla, el clip sale como lo eligió la IA)
                    print(f"  Gancho: no pude mejorarlo ({type(e).__name__}: {str(e)[:100]})", flush=True)
            render_clip(video, words, m["start"], m["end"], out, work, custom_crop=custom_crop, layout=clip_layout, brand=logo,
                        hook=m.get("hook") or m["title"], profile=prof, opts=opts)

            txt = " ".join(w["w"] for w in words if m["start"] <= w["start"] <= m["end"])
            if config.PACK:     # textos por red + 3 ganchos alternativos
                m["pack"] = packager.build_pack(m, txt, ocfg)
            thumb_text = m.get("hook") or m["title"]
            if config.VIRAL:    # Área viral: mejor título, hashtags, puntaje y veredicto ANTES de publicar
                v = viral.run(m, txt, ocfg, m["end"] - m["start"])
                m["viral"], m["viral_status"] = v, viral.status_for(v)
                m["hashtags"] = v["hashtags"]
                if config.VIRAL_AUTO_TITLE:
                    m["title"] = v["title"]
                if m.get("pack"):
                    viral.apply_to_pack(m["pack"], v)
                thumb_text = v["thumb_text"]
                print(f"  Viral: {v['score']} pts → {v['verdict']}" + (f" · riesgos: {', '.join(v['risks'])}" if v["risks"] else ""), flush=True)
            if config.THUMBS:   # miniatura del clip YA renderizado (antes de la tarjeta de intro/cierre)
                variants = [(0, "thumb_path", thumb_text)]
                if config.VIRAL and config.VIRAL_THUMB_AB:
                    tt = (m.get("viral") or {}).get("thumb_texts") or []
                    variants.append((1, "thumb_b_path", tt[1] if len(tt) > 1 else thumb_text))
                for rank, key, ttext in variants:
                    suffix = "" if rank == 0 else "_b"
                    jpg = thumb.make(out, ttext, work / f"{cid}{suffix}.jpg", rank=rank)
                    if jpg:
                        try:
                            db.upload_thumb(f"thumbs/{sid}/{cid}{suffix}.jpg", jpg)
                            m[key] = f"thumbs/{sid}/{cid}{suffix}.jpg"
                        except Exception as e:  # noqa: BLE001
                            print(f"  Miniatura: no pude subirla ({type(e).__name__}: {str(e)[:80]})", flush=True)
                        jpg.unlink(missing_ok=True)

            if ocfg["enabled"] and opts.get("original", True):
                try:   # aporte propio: voz narradora, dramómetro, encuesta A/B y descripción con tu punto de vista
                    raw = work / f"{cid}_raw.mp4"
                    shutil.copy(out, raw)
                    ex = original.extras(txt, ocfg)
                    wrapped = work / f"{cid}_orig.mp4"
                    original.wrap_clip(out, ex, wrapped, work, ocfg, score=m.get("score", 75))
                    out.unlink(missing_ok=True)
                    wrapped.rename(out)
                    m["description"] = original.description(m, ex, ocfg)
                    made.append((m.get("score", 0), m["title"], raw, dict(m)))
                except Exception as e:  # noqa: BLE001  (si falla, sube el clip normal)
                    print(f"  Modo Original: no pude envolver el clip ({type(e).__name__}: {str(e)[:120]})", flush=True)
            path = f"{sid}/{cid}.mp4"
            db.upload_clip(path, out)
            m["abs_start"], m["abs_end"] = m["start"] + offset, m["end"] + offset
            sync = config.SUB_SYNC_OFFSET
            in_clip = [{"w": w["w"], "start": w["start"] - m["start"] + sync, "end": w["end"] - m["start"] + sync}
                       for w in words if m["start"] <= w["start"] <= m["end"]]
            db.save_clip(sid, src.get("user_id"), m, path, out.stat().st_size, in_clip)
            gate_ok = ((not config.VIRAL) or (m.get("viral") or {}).get("verdict") == "ready") and not db.require_approval()   # solo lo que pasó el área viral (y con tu aprobación si la pediste)
            if config.FB_AUTOPUBLISH and gate_ok and published < config.FB_MAX_PER_JOB and m.get("score", 0) >= config.FB_MIN_SCORE:
                if publisher.publish_reel(out, packager.caption_for(m, "reels") if m.get("pack") else (m.get("description") or m["title"])):
                    published += 1
            out.unlink(missing_ok=True)
            print(f"  clip listo: {m['title']} ({m['score']}%)", flush=True)

        if ocfg["enabled"] and ocfg["top"] and len(made) >= 3:
            try:   # TOP automático con cuenta regresiva (#N … #1)
                best = sorted(made, key=lambda x: -x[0])[: ocfg["top_n"]]
                best = list(reversed(best))
                cid = str(uuid.uuid4())
                out = work / f"{cid}.mp4"
                head = f"TOP {len(best)} MOMENTOS"
                original.compilation([(t, p) for _, t, p, _m in best], head, out, work, ocfg)
                mm = dict(best[-1][3])
                mm.update({"title": f"{head}: {best[-1][1]}"[:80], "reason": "Compilación automática de los mejores momentos",
                           "description": original.description(mm, {"caption": f"Los {len(best)} mejores momentos de {ocfg['show']}. ¿Cuál fue el tuyo?"}, ocfg)})
                path = f"{sid}/{cid}.mp4"
                db.upload_clip(path, out)
                db.save_clip(sid, src.get("user_id"), mm, path, out.stat().st_size, [])
                print(f"  TOP listo: {head}", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"  TOP: no pude armarlo ({type(e).__name__}: {str(e)[:120]})", flush=True)

        db.set_source(sid, status="done")
        db.finish_job(job["id"], ok=True)
        print(f"Resumen: {len(chosen)} clip(s) · {st.summary()}", flush=True)
    except Cancelled:
        print(f"  fuente {sid} quitada desde la web, cancelo.", flush=True)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        fail(job, e, source_id=sid)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def fail(job, exc, source_id=None):
    jobq.fail(job, exc, source_id)


def handle(job):
    """Reparte el trabajo al módulo que corresponde, con sus logs etiquetados."""
    with logx.job(job["id"], job["type"]):
        print(f"Trabajo {job['id']} → fuente {job['source_id']} · prioridad {job.get('priority', 0)} · intento {job.get('attempts', 1)}", flush=True)
        if job["type"] == "record":
            live.process_live(job)
        elif job["type"] == "transform":
            process_transform(job)
        elif job["type"] == "text_to_video":
            ai_video.process_text_to_video(job)
        elif job["type"] == "clip":
            if (job.get("payload") or {}).get("preview"):
                import preview
                preview.process_preview(job)
            else:
                rerender.process_rerender(job)
        else:
            process(job)


def main():
    logx.install()
    lifecycle.install_signals()   # docker stop = salida ordenada
    lifecycle.start_watchdog()    # latido para el HEALTHCHECK de Docker
    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        raise SystemExit("Falta SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
    selfcheck.run()
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    import llm
    print(f"IA en orden de uso: {' → '.join(llm.configured())}", flush=True)
    print("Worker listo (encuadres, directos con chat, Modo Transformar y Crear con IA), esperando trabajos…", flush=True)
    if config.RECOVER_ON_START:
        try:
            n = db.recover_on_start()
            if n:
                print(f"Recuperación: {n} trabajo(s) que quedaron a medias vuelven a la cola.", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"Recuperación al arrancar: no pude ({type(e).__name__}: {str(e)[:100]})", flush=True)
    poster.start_thread()   # publica a su hora aunque el worker esté grabando un directo
    studio.start_thread()   # atiende Hacerlo viral (miniaturas, re-análisis) sin esperar a que termine un render
    last_clean = 0.0
    while True:
        try:
            db.apply_connections()    # llaves guardadas en la web (Conectar cuentas)
        except Exception:  # noqa: BLE001
            pass
        # Verificar cookies de YouTube cada 10 minutos
        if time.time() - getattr(main, "_last_cookie_check", 0) > 600:
            main._last_cookie_check = time.time()
            if config.COOKIES_FILE:
                from pathlib import Path
                cp = Path(config.COOKIES_FILE)
                if not cp.exists():
                    print(f"  ⚠ Archivo de cookies no encontrado: {config.COOKIES_FILE}", flush=True)
        db.BASE_INFO = {"auto_queue": db.auto_queue_on(), "discover": db.discover_on(), "switches": True, "networks": autoqueue.networks_available(),
                        "stats": config.STATS, "learn_slots": config.LEARN_SLOTS, "learn_min_posts": config.LEARN_MIN_POSTS}
        db.heartbeat()
        if time.time() - last_clean > 600:
            db.requeue_stale()
            last_clean = time.time()
        job = db.claim_job()
        if job:
            try:
                handle(job)
            except Exception as e:  # noqa: BLE001  (un error raro en un trabajo nunca debe apagar al worker)
                traceback.print_exc()
                print(f"  ✖ Error fuera de lo esperado en el trabajo: {type(e).__name__}: {str(e)[:150]}", flush=True)
                try:
                    db.finish_job(job["id"], ok=False, error=f"{type(e).__name__}: {e}")
                except Exception:  # noqa: BLE001
                    pass
                time.sleep(config.POLL_SECONDS)
        else:
            if lifecycle.daily_restart_due(db):
                lifecycle.main_exit(f"diario, {config.RESTART_HOUR}:00")    # Docker lo vuelve a levantar con el yt-dlp más nuevo
            try:
                viral.tick()        # analiza clips que llegaron sin pasar por el área viral (en vivo, rehechos)
            except Exception as e:  # noqa: BLE001
                print(f"Viral: error ({type(e).__name__}: {str(e)[:100]})", flush=True)
            try:
                discover.tick()     # ¿hay videos nuevos y fuertes en tus fuentes? (solo con DISCOVER=1)
            except Exception as e:  # noqa: BLE001
                print(f"Clips automáticos: error ({type(e).__name__}: {str(e)[:100]})", flush=True)
            try:
                watcher.tick()      # ¿alguno de tus canales entró en vivo? (solo cuando el worker está libre)
            except Exception as e:  # noqa: BLE001  (vigilar canales es un extra: nunca debe tumbar al worker)
                print(f"Canales automáticos: error ({type(e).__name__}: {str(e)[:100]})", flush=True)
            time.sleep(config.POLL_SECONDS)


if __name__ == "__main__":
    main()
