"""Worker de ClipForge: toma jobs 'download' (videos) y 'record' (directos) y produce clips verticales."""
import shutil
import time
import traceback
import uuid

import config
import db
import detect
import discover
from analyze import find_moments
from download import download
import live
import rerender
import selfcheck
import watcher
import brand
import energy
import jobq
import logx
import voices
import profiles
import original
import publisher
import autoqueue
import poster
import scheduler
import packager
import thumb
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
            in_clip = [{"w": w["w"], "start": w["start"] - m["start"], "end": w["end"] - m["start"]}
                       for w in words if m["start"] <= w["start"] <= m["end"]]
            db.save_clip(sid, src.get("user_id"), m, path, out.stat().st_size, in_clip)
            gate_ok = (not config.VIRAL) or (m.get("viral") or {}).get("verdict") == "ready"   # solo lo que pasó el área viral
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
    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        raise SystemExit("Falta SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY")
    selfcheck.run()
    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    import llm
    print(f"IA en orden de uso: {' → '.join(llm.configured())}", flush=True)
    print("Worker listo (encuadres: vertical, dividido, dos personas, difuminado; directos con reconexión y chat), esperando trabajos…", flush=True)
    poster.start_thread()   # publica a su hora aunque el worker esté grabando un directo
    last_clean = 0.0
    while True:
        db.BASE_INFO = {"auto_queue": config.AUTO_QUEUE, "discover": config.DISCOVER, "networks": autoqueue.networks_available()}
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
