"""Corta un tramo, lo pone vertical 9:16 y le quema subtítulos palabra por palabra."""
import subprocess
from pathlib import Path

import config

ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Cap,DejaVu Sans,86,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,2,2,60,60,520,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

# En modo pantalla dividida los subtítulos se suben (MargenV 820) para que no tapen la cara de abajo
ASS_HEADER_SPLIT = ASS_HEADER.replace("60,60,520,1", "60,60,820,1")

YELLOW = "{\\c&H00E0FF&}"  # ASS usa BGR
WHITE = "{\\c&HFFFFFF&}"


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_ass(words, start, end, group=3, is_split=False):
    """words: lista global [{w,start,end}]. Genera eventos relativos al inicio del clip."""
    ws = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.3]
    lines = [ASS_HEADER_SPLIT if is_split else ASS_HEADER]
    for i in range(0, len(ws), group):
        g = ws[i : i + group]
        for j, w in enumerate(g):
            t0 = w["start"] - start
            t1 = (g[j + 1]["start"] if j + 1 < len(g) else w["end"]) - start
            if t1 <= t0:
                t1 = t0 + 0.1
            text = " ".join(
                (YELLOW if k == j else WHITE) + x["w"].upper().replace("{", "(").replace("}", ")")
                for k, x in enumerate(g)
            )
            lines.append(f"Dialogue: 0,{_t(t0)},{_t(t1)},Cap,,0,0,0,,{text}\n")
    return "".join(lines)


def _probe(path: Path):
    """(ancho, alto) del video. Si falla, asume 1920x1080 para que el clip no se cancele."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split("x")[:2]
        return int(w), int(h)
    except (ValueError, IndexError):
        # Si no puede leer el tamaño (típico en modo en vivo), usa Full HD por defecto
        print(f"  Aviso: no pude leer el tamaño de {path.name}, usando 1920x1080 por defecto.", flush=True)
        return 1920, 1080


def _bitrate(dur: float) -> int:
    """Bitrate de video más alto posible sin pasar ~44 MB por clip (límite de 50 MB del plan gratis de Supabase)."""
    total = 44_000_000 * 8 / max(dur, 1.0)
    return int(min(12_000_000, max(3_000_000, total - 192_000)))


def _crop_filter(source: Path, start: float, dur: float):
    """Recorte 9:16 hecho en la resolución ORIGINAL (sin agrandar nada) y después un solo escalado nítido."""
    sw, sh = _probe(source)
    if sw / sh > 9 / 16:                     # video horizontal (lo normal): se recorta el ancho
        cw, ch = int(sh * 9 / 16) // 2 * 2, sh
        crop_frac = cw / sw
        keys = None
        if config.CLIP_FRAMING == "auto":
            import framing
            keys = framing.camera_keys(source, start, dur, sw, sh, crop_frac)
            if keys:
                moves = max(0, len(keys) - 1) // 2
                print(f"  Encuadre: sigo a la persona ({moves} cambio(s) de cámara)", flush=True)
        if keys:
            import framing
            xexpr = framing.x_expression(keys)
        else:
            xexpr = f"(iw-ow)*{config.CLIP_FOCUS_X:.3f}"
        return f"crop=w={cw}:h={ch}:x='{xexpr}':y=0"
    ch, cw = int(sw * 16 / 9) // 2 * 2, sw   # video ya vertical o cuadrado: se recorta el alto, centrado
    return f"crop=w={cw}:h={min(ch, sh)}:x=0:y='(ih-oh)/2'"


def render_clip(source: Path, words, start: float, end: float, out: Path, workdir: Path):
    dur = end - start

    if config.CLIP_LAYOUT == "blur":
        ass = workdir / f"{out.stem}.ass"
        ass.write_text(build_ass(words, start, end), encoding="utf-8")
        vf = (
            "split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5[b];"
            "[fg]scale=1080:-2:flags=lanczos[f];"
            "[b][f]overlay=(W-w)/2:(H-h)/2,subtitles={sub}"
        )
    elif config.CLIP_LAYOUT == "split":
        ass = workdir / f"{out.stem}.ass"
        ass.write_text(build_ass(words, start, end, is_split=True), encoding="utf-8")
        # MODO SPLIT SCREEN (Pantalla dividida)
        vf = (
            "split=2[top][bottom];"
            "[top]crop=iw:ih/2:0:0,scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[t];"
            "[bottom]crop=iw:ih/2:0:ih/2,scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960[b];"
            "[t][b]vstack,subtitles={sub}"
        )
    else:
        # MODO CROP
        ass = workdir / f"{out.stem}.ass"
        ass.write_text(build_ass(words, start, end), encoding="utf-8")
        sharpen = f"unsharp=5:5:{config.CLIP_SHARPEN:.2f}:5:5:0.0," if config.CLIP_SHARPEN > 0 else ""
        vf = (
            _crop_filter(source, start, dur)
            + ",scale=1080:1920:flags=lanczos+accurate_rnd+full_chroma_int,"
            + sharpen
            + "setsar=1,subtitles={sub}"
        )
    vf = vf.format(sub=ass.name)

    vb = _bitrate(dur)
    cmd = [
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(source.resolve()),
        "-vf", vf,
        "-c:v", "libx264", "-preset", config.CLIP_PRESET, "-crf", str(config.CLIP_CRF),
        "-profile:v", "high", "-level", "4.2",
        "-maxrate", str(vb), "-bufsize", str(vb * 2),
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(out.resolve()),
    ]
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg falló: " + r.stderr[-600:])
    return out