"""Corta un tramo, lo pone vertical 9:16 y le quema subtítulos palabra por palabra."""
import re
import subprocess
from pathlib import Path

import config

# ---------------------------------------------------------------- subtítulos (ASS)
# Estilo por defecto = "Clásico". La web (Ajustes > Subtítulos) manda sus valores en brand["subs"].
DEFAULT_SUBS = {"text": "FFFFFF", "active": "FFE000", "outline": "000000", "size": 86, "outline_w": 7,
                "upper": True, "pop": True, "offset": 0}

# Medidas de los encuadres (suman 1920)
# Dividido: alto (px) del panel de ARRIBA (tu cara). Abajo va el gameplay con el resto.
#   split      cara grande: gameplay completo en 16:9 (1080x608), sin recortar
#   split_eq   equilibrado: ~50/50, el gameplay se recorta un poco de los lados
#   split_game juego grande: el gameplay ocupa ~60% (recorta más de los lados)
SPLIT_TOPS = {"split": 1312, "split_eq": 1000, "split_game": 780}
DUO_H = 960   # dos personas: dos paneles iguales de 1080x960

# Altura (MargenV) de los subtítulos según el encuadre: en dividido y dos personas quedan a caballo sobre la unión
SUB_MARGIN = {"crop": 520, "blur": 520, "duo": 890}


def _hex(c: str, default: str = "FFFFFF") -> str:
    """'#RRGGBB' -> 'BBGGRR' (ASS usa BGR)."""
    c = str(c or "").lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", c):
        c = default
    return (c[4:6] + c[2:4] + c[0:2]).upper()


def _subs(style):
    st = {**DEFAULT_SUBS, **{k: v for k, v in (style or {}).items() if v is not None}}
    st["size"] = int(min(140, max(40, float(st["size"]))))
    st["outline_w"] = int(min(14, max(0, float(st["outline_w"]))))
    st["offset"] = int(min(600, max(-400, float(st["offset"]))))
    return st


def _header(layout: str, st: dict) -> str:
    base = SUB_MARGIN.get(layout) or (1920 - SPLIT_TOPS[layout] - 30 if layout in SPLIT_TOPS else 520)
    margin = max(40, base + st["offset"])
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Cap,DejaVu Sans,{st['size']},&H00{_hex(st['text'])},&H00{_hex(st['text'])},&H00{_hex(st['outline'], '000000')},&H80000000,-1,0,0,0,100,100,0,0,1,{st['outline_w']},2,2,60,60,{margin},1
Style: Hook,DejaVu Sans,64,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,16,0,8,90,90,230,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""


def _t(sec: float) -> str:
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _esc(text: str, upper: bool) -> str:
    text = text.upper() if upper else text
    return text.replace("{", "(").replace("}", ")").replace("\\", "/")


def build_ass(words, start, end, group=3, layout="crop", style=None, hook=None, hook_sec=3.5):
    """words: lista global [{w,start,end}]. Genera eventos relativos al inicio del clip.
    hook = frase gancho que sale arriba los primeros `hook_sec` segundos (None = sin gancho)."""
    st = _subs(style)
    ws = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.3]
    lines = [_header(layout, st)]

    yellow = "{\\c&H" + _hex(st["active"], "00E0FF") + "&}"
    white = "{\\c&H" + _hex(st["text"]) + "&}"
    pop = "{\\fscx120\\fscy120\\t(0,100,\\fscx100\\fscy100)}" if st["pop"] else ""

    if hook and str(hook).strip():
        h = _esc(str(hook).strip()[:70], True)
        lines.append(f"Dialogue: 1,{_t(0.15)},{_t(max(1.0, min(hook_sec, end - start - 0.2)))},Hook,,0,0,0,,{h}\n")

    for i in range(0, len(ws), group):
        g = ws[i : i + group]
        for j, w in enumerate(g):
            t0 = w["start"] - start
            t1 = (g[j + 1]["start"] if j + 1 < len(g) else w["end"]) - start
            if t1 <= t0:
                t1 = t0 + 0.1
            partes = []
            for k, x in enumerate(g):
                partes.append((f"{yellow}{pop}" if k == j else white) + _esc(x["w"], st["upper"]))
            lines.append(f"Dialogue: 0,{_t(t0)},{_t(t1)},Cap,,0,0,0,,{' '.join(partes)}\n")
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


def _cam_box(source: Path, start: float, dur: float, sw: int, sh: int, custom_crop: dict = None, top_h: int = 1312) -> dict:
    """Recuadro (en %) de la cámara para el panel de arriba del modo dividido.
    Prioridad: el que marcó el usuario > detección de cara > esquina inferior derecha (donde suele estar la cámara)."""
    if custom_crop:
        return custom_crop
    aspect = 1080 / top_h
    if config.CLIP_FRAMING == "auto":
        import framing
        box = framing.cam_box(source, start, dur, sw, sh, aspect)
        if box:
            print("  Dividido: encontré la cámara por la cara", flush=True)
            return box
    print("  Dividido: no encontré la cámara, uso la esquina inferior derecha (márcala a mano en la web)", flush=True)
    w = 26.0
    h = min(100.0, w * sw / (sh * aspect))
    return {"x": 100 - w - 1, "y": 100 - h - 1, "w": w, "h": h}


def _duo_boxes(source: Path, start: float, dur: float, sw: int, sh: int):
    """(arriba, abajo): cada persona en su panel. Si no ve a dos personas, usa la mitad izquierda arriba y la derecha abajo."""
    aspect = 1080 / DUO_H
    if config.CLIP_FRAMING == "auto":
        import framing
        two = framing.duo_boxes(source, start, dur, sw, sh, aspect)
        if two:
            print("  Dos personas: encontré a las dos (izquierda/arriba va arriba)", flush=True)
            return two
    print("  Dos personas: no vi a dos personas claras, uso mitad izquierda arriba y mitad derecha abajo", flush=True)
    h = min(100.0, 50.0 * sw / (sh * aspect))
    return ({"x": 0.0, "y": (100 - h) / 2, "w": 50.0, "h": h}, {"x": 50.0, "y": (100 - h) / 2, "w": 50.0, "h": h})


def _ass_for(words, start, end, workdir: Path, stem: str, layout: str, brand: dict = None, hook: str = None) -> Path:
    ass = workdir / f"{stem}.ass"
    b = brand or {}
    ass.write_text(build_ass(words, start, end, layout=layout, style=b.get("subs"),
                             hook=hook if b.get("hook", True) else None, hook_sec=float(b.get("hook_sec", 3.5))),
                   encoding="utf-8")
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
    if layout == "duo":
        sw, sh = _probe(source)
        top, bot = _duo_boxes(source, start, dur, sw, sh)
        a, b = _box_filter(sw, sh, top), _box_filter(sw, sh, bot)
        return (
            "[0:v]split=2[a][b];"
            f"[a]{a},scale=1080:{DUO_H}:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:{DUO_H},setsar=1[t];"
            f"[b]{b},scale=1080:{DUO_H}:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:{DUO_H},setsar=1[g];"
            f"[t][g]vstack=inputs=2,subtitles={ass_name}"
        )
    if layout in SPLIT_TOPS:
        top_h = SPLIT_TOPS[layout]
        bot_h = 1920 - top_h
        sw, sh = _probe(source)
        cam = _box_filter(sw, sh, _cam_box(source, start, dur, sw, sh, custom_crop, top_h))
        if bot_h <= 640:   # cabe el gameplay completo en 16:9: sin recortar
            game = f"scale=1080:{bot_h}:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:{bot_h}:(ow-iw)/2:(oh-ih)/2:black"
        else:              # panel más alto: el gameplay llena el panel (recorta un poco de los lados)
            game = (f"{_fit_filter(sw, sh, 1080 / bot_h, config.CLIP_FOCUS_X)},"
                    f"scale=1080:{bot_h}:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:{bot_h}")
        return (
            "[0:v]split=2[a][b];"
            f"[a]{cam},scale=1080:{top_h}:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:{top_h},setsar=1[t];"
            f"[b]{game},setsar=1[g];"
            f"[t][g]vstack=inputs=2,subtitles={ass_name}"
        )
    sharpen = f"unsharp=5:5:{config.CLIP_SHARPEN:.2f}:5:5:0.0," if config.CLIP_SHARPEN > 0 else ""
    return (
        "[0:v]" + _crop_filter(source, start, dur, custom_crop)
        + ",scale=1080:1920:flags=lanczos+accurate_rnd+full_chroma_int,"
        + sharpen + f"setsar=1,subtitles={ass_name}"
    )


_LOGO_POS = {
    "bc": "(W-w)/2:H-h-{m}", "bl": "40:H-h-{m}", "br": "W-w-40:H-h-{m}",
    "tc": "(W-w)/2:60", "tl": "40:60", "tr": "W-w-40:60",
}


def _logo_graph(graph: str, brand: dict) -> str:
    """Pega el logo sobre el video. brand = {path, pos, size (% del ancho), opacity (0-100), margin}."""
    pos = _LOGO_POS.get(brand.get("pos", "bc"), _LOGO_POS["bc"]).format(m=int(brand.get("margin", 110)))
    width = max(40, int(1080 * min(60, max(5, float(brand.get("size", 24)))) / 100)) // 2 * 2
    alpha = min(1.0, max(0.1, float(brand.get("opacity", 100)) / 100))
    return (f"{graph}[v];[1:v]scale={width}:-1,format=rgba,colorchannelmixer=aa={alpha:.2f}[logo];"
            f"[v][logo]overlay={pos}:format=auto[out]")


def render_clip(source: Path, words, start: float, end: float, out: Path, workdir: Path,
                custom_crop: dict = None, layout: str = None, brand: dict = None, hook: str = None):
    dur = end - start
    layout = (layout or config.CLIP_LAYOUT or "crop").strip().lower()
    if layout not in ("crop", "blur", "duo", *SPLIT_TOPS):
        layout = "crop"

    ass = _ass_for(words, start, end, workdir, out.stem, layout, brand, hook)
    graph = build_filter(layout, source, start, dur, ass.name, custom_crop)

    logo = Path(brand["path"]) if brand and brand.get("path") else None
    if logo and logo.exists():
        graph = _logo_graph(graph, brand)
        inputs = ["-i", str(source.resolve()), "-i", str(logo.resolve())]
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
