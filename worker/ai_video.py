"""Crear con IA: prompt -> 4 escenas -> video vertical de 60 s (ffmpeg, sin MoviePy).

La API de Hugging Face devuelve clips cortos (2-3 s). Para llegar a 60 s sin pagar,
cada escena se repite con -stream_loop y se recorta a 15 s con ffmpeg.
"""
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import requests

import brand
import config
import db
import jobq
import logx
import render
from original import H, W, FPS, size_cap

STYLES = {
    "realista": "photorealistic, cinematic lighting, natural colors, 35mm film",
    "anime": "anime style, clean line art, vibrant colors, hand drawn illustration",
    "cyberpunk": "cyberpunk, neon lights, rainy night, futuristic city, high contrast",
    "cartoon": "colorful cartoon, soft shapes, family friendly animation",
    "3d": "3D render, pixar style, soft shadows, detailed materials",
}


class Cancelled(Exception):
    """La fuente se quitó desde la web mientras se generaba."""


def _esc(t):
    """Texto seguro para ASS (mismo criterio que original.py)."""
    t = "".join(ch for ch in str(t) if ord(ch) < 0x2190).strip()
    return t.replace("{", "(").replace("}", ")").replace("\\", "/").replace("\n", "\\N")


def _run(cmd, workdir, label="ffmpeg", timeout=900):
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"{label}: {(r.stderr or '')[-400:]}")
    return r


def _probe_duration(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except (ValueError, OSError, subprocess.SubprocessError):
        return 0.0


def _download_url(url, dest, workdir=None):
    dest = Path(dest)
    limit = 60 * 1024 * 1024
    with requests.get(url, stream=True, timeout=(10, config.IA_REQUEST_TIMEOUT)) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise RuntimeError("El clip generado supera los 60 MB; aborto la descarga.")
                f.write(chunk)
    if dest.stat().st_size < 1024:
        raise RuntimeError("El clip generado llegó vacío.")
    return dest


def _save_api_result(resp, dest):
    """La inference API puede devolver bytes de video o JSON con una URL."""
    ctype = resp.headers.get("content-type", "").lower()
    if "json" in ctype or resp.content[:1] in (b"{", b"["):
        data = resp.json()
        url = None
        if isinstance(data, dict):
            url = data.get("url") or (data.get("output") if isinstance(data.get("output"), str) else None)
        elif isinstance(data, list) and data:
            url = data[0] if isinstance(data[0], str) else None
        if not url:
            raise RuntimeError(f"La API respondió JSON sin video: {str(data)[:160]}")
        return _download_url(url, dest)
    dest.write_bytes(resp.content)
    if dest.stat().st_size < 1024:
        raise RuntimeError("La API devolvió un archivo de video vacío.")
    return dest


def _hf_generate(full_prompt, workdir, index):
    if not config.HF_TOKEN:
        raise RuntimeError("Falta HF_TOKEN en worker/.env (huggingface.co/settings/tokens).")
    url = f"https://api-inference.huggingface.co/models/{config.HF_MODEL}"
    headers = {"Authorization": f"Bearer {config.HF_TOKEN}"}
    body = {"inputs": full_prompt}
    last = None
    for attempt in range(1, config.IA_MAX_RETRIES + 1):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=(10, config.IA_REQUEST_TIMEOUT))
        except requests.RequestException as e:  # noqa: BLE001
            last = e
            print(f"  IA [{index + 1}] sin conexión ({type(e).__name__}); reintento {attempt}", flush=True)
            time.sleep(2)
            continue
        if r.status_code in (200, 201):
            return _save_api_result(r, workdir / f"ia_raw_{index}.mp4")
        if r.status_code in (429, 503):  # cold start / sin cupo
            wait = config.IA_MAX_WAIT
            try:
                data = r.json()
                if isinstance(data, dict) and data.get("estimated_time"):
                    wait = min(config.IA_MAX_WAIT, max(2, int(float(data["estimated_time"])) + 2))
            except Exception:  # noqa: BLE001
                pass
            last = RuntimeError(f"Hugging Face {r.status_code}: modelo cargando o sin cupo")
            print(f"  IA [{index + 1}] esperando {wait}s (intento {attempt}/{config.IA_MAX_RETRIES})…", flush=True)
            time.sleep(wait)
            continue
        last = RuntimeError(f"Hugging Face {r.status_code}: {r.text[:180]}")
        break
    raise last or RuntimeError("Hugging Face no respondió")


def _replicate_generate(full_prompt, workdir, index):
    """Plan B opcional: Replicate por REST (sin SDK). Requiere REPLICATE_VERSION."""
    if not (config.REPLICATE_API_TOKEN and config.REPLICATE_VERSION):
        raise RuntimeError("Replicate no configurado (REPLICATE_API_TOKEN + REPLICATE_VERSION).")
    auth = {"Authorization": f"Token {config.REPLICATE_API_TOKEN}"}
    r = requests.post(
        "https://api.replicate.com/v1/predictions",
        headers={**auth, "Content-Type": "application/json", "Prefer": "wait"},
        json={"version": config.REPLICATE_VERSION, "input": {"prompt": full_prompt, "fps": 8}},
        timeout=(10, 90),
    )
    r.raise_for_status()
    data = r.json()
    deadline = time.time() + config.IA_REQUEST_TIMEOUT
    status = data.get("status")
    while status not in ("succeeded", "failed", "canceled") and time.time() < deadline:
        get_url = (data.get("urls") or {}).get("get")
        if not get_url:
            break
        time.sleep(2)
        rr = requests.get(get_url, headers=auth, timeout=30)
        rr.raise_for_status()
        data = rr.json()
        status = data.get("status")
    if status != "succeeded":
        raise RuntimeError(f"Replicate terminó en {status}: {str(data.get('error'))[:160]}")
    out = data.get("output")
    url = out[0] if isinstance(out, list) and out else out
    if not isinstance(url, str):
        raise RuntimeError("Replicate no devolvió una URL de video.")
    return _download_url(url, workdir / f"ia_raw_{index}.mp4")


def _fetch_source_clip(full_prompt, workdir, index):
    try:
        return _hf_generate(full_prompt, workdir, index)
    except Exception as e:  # noqa: BLE001
        if not (config.REPLICATE_API_TOKEN and config.REPLICATE_VERSION):
            raise
        print(f"  IA [{index + 1}] Hugging Face falló ({str(e)[:120]}); pruebo Replicate.", flush=True)
        return _replicate_generate(full_prompt, workdir, index)


def _caption_ass(text, seconds):
    end = f"0:00:{seconds:05.2f}"
    head = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
        "Style: Cap,Montserrat,66,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,2,0,1,9,3,2,80,80,300,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    return head + f"Dialogue: 0,0:00:00.00,{end},Cap,,0,0,0,,{{\\fad(300,300)}}{_esc(text)}\n"


def _normalize_segment(raw, workdir, index, seconds, logo_cfg=None, caption=""):
    """Un clip corto cualquiera -> 1080x1920, `seconds` exactos, con logo, subtítulo y audio."""
    logo_cfg = logo_cfg or {}
    ass = workdir / f"ia_cap_{index}.ass"
    ass.write_text(_caption_ass(caption or " ", seconds), encoding="utf-8")
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
          f"crop={W}:{H},setsar=1,fps={FPS},subtitles={ass.name},format=yuv420p")
    out = workdir / f"ia_seg_{index}.mp4"
    cap = size_cap(config.IA_TOTAL_SECONDS)  # bitrate pensado para los 60 s completos

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(raw)]
    logo = Path(logo_cfg["path"]) if logo_cfg.get("path") else None
    has_logo = bool(logo and logo.exists())
    if has_logo:
        cmd += ["-i", str(logo)]   # render._logo_graph espera el logo en [1:v]
    audio_idx = 2 if has_logo else 1
    cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]

    if has_logo:
        graph = render._logo_graph(f"[0:v]{vf}[v]", logo_cfg, "v")
        cmd += ["-filter_complex", graph, "-map", "[out]", "-map", f"{audio_idx}:a:0"]
    else:
        cmd += ["-vf", vf, "-map", "0:v:0", "-map", f"{audio_idx}:a:0"]

    cmd += ["-t", f"{seconds:.2f}", "-frames:v", str(int(round(seconds * FPS))),
            "-c:v", "libx264", "-preset", config.CLIP_PRESET,
            "-crf", str(config.CLIP_CRF), "-maxrate", str(cap), "-bufsize", str(cap * 2),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart", str(out)]
    _run(cmd, workdir, "normalizar IA")
    return out


def generate_clip(prompt, style, duration=15, workdir=None, index=0, logo_cfg=None, caption=None):
    """API pública: genera un segmento vertical listo para concatenar."""
    workdir = Path(workdir or config.WORK_DIR)
    workdir.mkdir(parents=True, exist_ok=True)
    suffix = STYLES.get(str(style).lower(), STYLES["realista"])
    full_prompt = f"{prompt.strip()}. {suffix}"
    raw = _fetch_source_clip(full_prompt, workdir, index)
    norm = _normalize_segment(raw, workdir, index, duration, logo_cfg, caption)
    if raw != norm:
        raw.unlink(missing_ok=True)
    return norm


def _split_caption(prompt, n):
    words = str(prompt).split()
    if not words:
        return ["Clip generado con IA"] * n
    size = max(1, -(-len(words) // n))
    parts = [" ".join(words[i:i + size]) for i in range(0, len(words), size)]
    return [(parts[i] if i < len(parts) else parts[-1])[:110] for i in range(n)]


def _concat(paths, workdir):
    listing = workdir / "ia_concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in paths), encoding="utf-8")
    out = workdir / "ia_joined.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
          "-i", listing.name, "-c", "copy", "-movflags", "+faststart", str(out)], workdir, "unir clips")
    return out


def _add_music(video, workdir):
    total = config.IA_TOTAL_SECONDS
    fade_out = max(0, total - 3)
    out = workdir / "ia_music.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video.name]

    music = None
    if config.IA_MUSIC_URL:
        try:
            music = _download_url(config.IA_MUSIC_URL, workdir / "ia_music.bin")
        except Exception as e:  # noqa: BLE001
            print(f"  IA: no pude bajar la música ({type(e).__name__}); uso un pad sintetizado.", flush=True)

    if music:
        cmd += ["-stream_loop", "-1", "-i", music.name]
        filt = (f"[0:a][1:a]amix=inputs=2:duration=first,volume=1.3,"
                f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out}:d=3[a]")
    else:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=110:sample_rate=48000",
                "-f", "lavfi", "-i", "sine=frequency=164.81:sample_rate=48000",
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000"]
        filt = ("[1:a]volume=0.10[a1];[2:a]volume=0.06[a2];[3:a]volume=0.04[a3];"
                f"[0:a][a1][a2][a3]amix=inputs=4:duration=first,lowpass=f=1000,"
                f"afade=t=in:st=0:d=2,afade=t=out:st={fade_out}:d=3[a]")

    cmd += ["-filter_complex", filt, "-map", "0:v:0", "-map", "[a]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}",
            "-movflags", "+faststart", str(out)]
    _run(cmd, workdir, "música")
    return out


def _force_duration(video, workdir):
    """Seguridad: el MP4 entregado dura exactamente IA_TOTAL_SECONDS."""
    total = config.IA_TOTAL_SECONDS
    out = workdir / "ia_final.mp4"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", video.name, "-t", f"{total:.2f}",
          "-c", "copy", "-movflags", "+faststart", str(out)], workdir, "ajustar duración")
    return out


def process_text_to_video(job):
    """Encola -> 4 escenas -> 60 s -> Storage + tabla clips."""
    sid = job["source_id"]
    src = db.get_source(sid) or {}
    payload = job.get("payload") or {}
    prompt = str(payload.get("prompt") or src.get("title") or "").strip()[:600]
    style = str(payload.get("style") or config.IA_STYLE_DEFAULT).strip().lower()
    music = str(payload.get("music")).lower() not in ("0", "false", "no", "off", "none")
    work = config.WORK_DIR / sid
    work.mkdir(parents=True, exist_ok=True)
    st = logx.Stages()
    total = config.IA_TOTAL_SECONDS

    def alive():
        if not db.source_exists(sid):
            raise Cancelled()

    try:
        if int(job.get("attempts") or 1) > 1:
            n = db.reset_source_outputs(sid)
            print(f"  Reintento: limpié {n} clip(s) a medias del intento anterior", flush=True)

        st.begin("generación")
        db.set_source(sid, status="downloading", error=None)
        logo_cfg = brand.load(work, template=payload.get("brand_template"))
        captions = _split_caption(prompt, config.IA_CLIPS)
        parts = []
        for i in range(config.IA_CLIPS):
            alive()
            print(f"  IA: escena {i + 1}/{config.IA_CLIPS}…", flush=True)
            parts.append(generate_clip(prompt, style, duration=config.IA_CLIP_SECONDS,
                                       workdir=work, index=i, logo_cfg=logo_cfg,
                                       caption=captions[i]))
            db.set_source(sid, status="analyzing")

        st.begin("ensamblado")
        joined = _concat(parts, work)
        with_music = _add_music(joined, work) if music else joined
        final = _force_duration(with_music, work)
        alive()

        st.begin("subida")
        cid = str(uuid.uuid4())
        path = f"{sid}/{cid}.mp4"
        db.upload_clip(path, final)
        m = {
            "title": prompt[:100] or "Video generado con IA",
            "score": 75,
            "reason": "Video vertical generado con IA a partir de un prompt, con subtítulos y marca propia.",
            "abs_start": 0.0,
            "abs_end": _probe_duration(final) or total,
            "description": f"{prompt}\n\nEstilo: {style}" + (" · música de fondo" if music else ""),
        }
        db.save_clip(sid, src.get("user_id"), m, path, final.stat().st_size, [])
        db.set_source(sid, status="done", title=m["title"])
        db.finish_job(job["id"], ok=True)
        print(f"Video IA listo: {m['title']} ({m['abs_end']:.0f} s) · {st.summary()}", flush=True)
    except Cancelled:
        print(f"  fuente {sid} quitada desde la web, cancelo.", flush=True)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        jobq.fail(job, e, source_id=sid)
    finally:
        shutil.rmtree(work, ignore_errors=True)
