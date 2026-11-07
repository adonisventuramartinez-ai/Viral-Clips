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

YELLOW = "{\\c&H00E0FF&}"  # ASS usa BGR
WHITE = "{\\c&HFFFFFF&}"


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def build_ass(words, start, end, group=3):
    """words: lista global [{w,start,end}]. Genera eventos relativos al inicio del clip."""
    ws = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.3]
    lines = [ASS_HEADER]
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


def render_clip(source: Path, words, start: float, end: float, out: Path, workdir: Path):
    ass = workdir / f"{out.stem}.ass"
    ass.write_text(build_ass(words, start, end), encoding="utf-8")

    if config.CLIP_LAYOUT == "crop":
        vf = "scale=-2:1920,crop=1080:1920,subtitles={sub}"
    else:
        vf = (
            "split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5[b];"
            "[fg]scale=1080:-2[f];"
            "[b][f]overlay=(W-w)/2:(H-h)/2,subtitles={sub}"
        )
    vf = vf.format(sub=ass.name)

    cmd = [
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", str(source.resolve()),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-maxrate", "6M", "-bufsize", "12M",  # mantiene cada clip bajo ~50 MB (límite del plan gratis de Supabase)
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        str(out.resolve()),
    ]
    # cwd=workdir para que el filtro subtitles encuentre el .ass sin escapar rutas
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg falló: " + r.stderr[-600:])
    return out
