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

# En modo dividido los subtítulos quedan sobre la unión de los dos paneles (MargenV 1000)
ASS_HEADER_SPLIT = ASS_HEADER.replace("60,60,520,1", "60,60,1000,1")

# Medidas del modo dividido (suman 1920): arriba la cámara, abajo el juego
SPLIT_TOP_H = 760
SPLIT_BOT_H = 1920 - SPLIT_TOP_H

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
    
    POP_EFFECT = "{\\fscx120\\fscy120\\t(0,100,\\fscx100\\fscy100)}"

    for i in range(0, len(ws), group):
        g = ws[i : i + group]
        for j, w in enumerate(g):
            t0 = w["start"] - start
            t1 = (g[j + 1]["start"] if j + 1 < len(g) else w["end"]) - start
            if t1 <= t0:
                t1 = t0 + 0.1
            
            partes = []
            for k, x in enumerate(g):
                if k == j:
                    partes.append(f"{YELLOW}{POP_EFFECT}{x['w'].upper().replace('{', '(').replace('}', ')')}")
                else:
                    partes.append(f"{WHITE}{x['w'].upper().replace('{', '(').replace('}', ')')}")
            
            text = " ".join(partes)
            lines.append(f"Dialogue: 0,{_t(t0)},{_t(t1)},Cap,,0,0,0,,{text}\n")
    return "".join(lines)


def _probe(path: Path):
    """(ancho, alto) del video. Si falla, asume 1920x1080."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True)
    try:
        w, h = r.stdout.strip().split("x")[:2]
        return int(w), int(h)
    except (ValueError, IndexError):
        print(f"  Aviso: no pude leer el tamaño de {path.name}, usando 1920x1080 por defecto.", flush=True)
        return 1920, 1080


def _bitrate(dur: float) -> int:
    total = 44_000_000 * 8 / max(dur, 1.0)
    return int(min(12_000_000, max(3_000_000, total - 192_000)))


def _even(v: float) -> int:
    return max(2, int(v) // 2 * 2)


def _box_filter(sw: int, sh: int, box: dict) -> str:
    """Recuadro en % del video -> filtro crop de ffmpeg (siempre dentro del cuadro y con medidas pares)."""
    cw = min(sw, _even(sw * float(box["w"]) / 100))
    ch = min(sh, _even(sh * float(box["h"]) / 100))
    x = min(sw - cw, max(0, int(sw * float(box["x"]) / 100) // 2 * 2))
    y = min(sh - ch, max(0, int(sh * float(box["y"]) / 100) // 2 * 2))
    return f"crop=w={cw}:h={ch}:x={x}:y={y}"


def _fit_filter(sw: int, sh: int, aspect: float, fx: float = 0.5) -> str:
    """Recorte de la proporción `aspect` (ancho/alto) lo más grande posible; fx = 0 izquierda, 1 derecha."""
    if sw / sh > aspect:
        cw, ch = min(sw, _even(sh * aspect)), sh
    else:
        cw, ch = sw, min(sh, _even(sw / aspect))
    return f"crop=w={cw}:h={ch}:x='(iw-ow)*{fx:.3f}':y='(ih-oh)/2'"


def _crop_filter(source: Path, start: float, dur: float, custom_crop: dict = None):
    """Modo vertical: recorte 9:16 manual, siguiendo caras, o centrado."""
    sw, sh = _probe(source)

    if custom_crop:
        return _box_filter(sw, sh, custom_crop)

    if sw / sh > 9 / 16:
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
    ch, cw = int(sw * 16 / 9) // 2 * 2, sw
    return f"crop=w={cw}:h={min(ch, sh)}:x=0:y='(ih-oh)/2'"


def _cam_box(source: Path, start: float, dur: float, sw: int, sh: int, custom_crop: dict = None) -> dict:
    """Recuadro (en %) de la cámara para el panel de arriba del modo dividido.
    Prioridad: el que marcó el usuario > detección de cara > esquina inferior derecha (donde suele estar la cámara)."""
    if custom_crop:
        return custom_crop
    aspect = 1080 / SPLIT_TOP_H
    if config.CLIP_FRAMING == "auto":
        import framing
        box = framing.cam_box(source, start, dur, sw, sh, aspect)
        if box:
            print("  Dividido: encontré la cámara por la cara", flush=True)
            return box
    print("  Dividido: no encontré la cámara, uso la esquina inferior derecha (márcala a mano en la web)", flush=True)
    w = 30.0
    h = min(100.0, w * sw / (sh * aspect))
    return {"x": 100 - w - 1, "y": 100 - h - 1, "w": w, "h": h}


def _ass_for(words, start, end, workdir: Path, stem: str, split: bool) -> Path:
    ass = workdir / f"{stem}.ass"
    ass.write_text(build_ass(words, start, end, is_split=split), encoding="utf-8")
    return ass


def build_filter(layout: str, source: Path, start: float, dur: float, ass_name: str, custom_crop: dict = None) -> str:
    """Devuelve el grafo de filtros (sin etiqueta final) para el encuadre pedido."""
    if layout == "blur":
        return (
            "[0:v]split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,eq=brightness=-0.12[b];"
            "[fg]scale=1080:-2:flags=lanczos[f];"
            f"[b][f]overlay=(W-w)/2:(H-h)/2,setsar=1,subtitles={ass_name}"
        )
    if layout == "split":
        sw, sh = _probe(source)
        cam = _box_filter(sw, sh, _cam_box(source, start, dur, sw, sh, custom_crop))
        game = _fit_filter(sw, sh, 1080 / SPLIT_BOT_H, config.CLIP_FOCUS_X)
        return (
            "[0:v]split=2[a][b];"
            f"[a]{cam},scale=1080:{SPLIT_TOP_H}:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:{SPLIT_TOP_H},setsar=1[t];"
            f"[b]{game},scale=1080:{SPLIT_BOT_H}:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:{SPLIT_BOT_H},setsar=1[g];"
            f"[t][g]vstack=inputs=2,subtitles={ass_name}"
        )
    sharpen = f"unsharp=5:5:{config.CLIP_SHARPEN:.2f}:5:5:0.0," if config.CLIP_SHARPEN > 0 else ""
    return (
        "[0:v]" + _crop_filter(source, start, dur, custom_crop)
        + ",scale=1080:1920:flags=lanczos+accurate_rnd+full_chroma_int,"
        + sharpen + f"setsar=1,subtitles={ass_name}"
    )


def render_clip(source: Path, words, start: float, end: float, out: Path, workdir: Path,
                custom_crop: dict = None, layout: str = None):
    dur = end - start
    layout = (layout or config.CLIP_LAYOUT or "crop").strip().lower()
    if layout not in ("crop", "split", "blur"):
        layout = "crop"

    ass = _ass_for(words, start, end, workdir, out.stem, split=(layout == "split"))
    graph = build_filter(layout, source, start, dur, ass.name, custom_crop)

    logo = (workdir / config.LOGO_PATH) if getattr(config, "LOGO_PATH", "") else None
    if logo and logo.exists():
        graph = f"{graph}[v];[1:v]scale=150:-1[logo];[v][logo]overlay=W-w-20:20[out]"
        inputs = ["-i", str(source.resolve()), "-i", str(logo)]
    else:
        graph = f"{graph}[out]"
        inputs = ["-i", str(source.resolve())]

    vb = _bitrate(dur)
    cmd = [
        "ffmpeg", "-y", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}",
    ] + inputs + [
        "-filter_complex", graph, "-map", "[out]", "-map", "0:a?",
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
