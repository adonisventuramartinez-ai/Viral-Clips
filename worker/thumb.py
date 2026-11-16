"""Miniatura automática: elige el mejor cuadro del clip (nítido, con cara, bien iluminado) y le pone el título encima.

  pick_time(video)         -> segundo del mejor cuadro
  make(video, title, out)  -> ruta del JPG 1080x1920 (o None si algo falla; nunca tumba el trabajo)
"""
import glob
import subprocess
from pathlib import Path

N_FRAMES = 10
W, H = 1080, 1920
# Estilos del texto de la miniatura. key = color de la palabra más larga (None = todo blanco), pos = dónde empieza el texto (fracción del alto),
# fade = desde dónde empieza el degradado negro que ayuda a leer; top = el degradado y el texto van arriba.
STYLES = {
    "amarillo": {"key": (255, 224, 0), "pos": 0.55, "fade": 0.40, "top": False},
    "rojo": {"key": (255, 45, 79), "pos": 0.55, "fade": 0.40, "top": False},
    "blanco": {"key": None, "pos": 0.55, "fade": 0.40, "top": False},
    "centro": {"key": (255, 224, 0), "pos": 0.38, "fade": 0.25, "top": False},
}
DEFAULT_STYLE = "amarillo"


def style_of(name):
    return STYLES.get(str(name or "").lower(), STYLES[DEFAULT_STYLE])
FONTS = ["/usr/share/fonts/truetype/**/Montserrat*Bold*.ttf", "/usr/share/fonts/**/Montserrat-ExtraBold*.ttf",
         "/usr/share/fonts/truetype/**/Poppins-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "C:/Windows/Fonts/arialbd.ttf"]


def score_frame(sharp, face_w, face_x, mean):
    """Puntaje de un cuadro (lógica pura). sharp = nitidez (varianza del laplaciano), face_w/face_x = ancho y posición de la cara
    como fracción del cuadro (None si no hay cara), mean = brillo medio 0-255."""
    s = min(1.0, sharp / 300.0)
    face = 0.0
    if face_w:
        face = 1.0 if 0.12 <= face_w <= 0.55 else 0.5
        if face_x is not None and abs(face_x - 0.5) > 0.3:
            face *= 0.6   # cara pegada al borde: queda mal con el texto y la interfaz de la red
    light = 1.0 if 45 <= mean <= 200 else (0.4 if 25 <= mean < 45 or 200 < mean <= 235 else 0.0)
    return 1.0 * s + 1.6 * face + 0.8 * light


def _frames(video, dur, n=N_FRAMES):
    """[(segundo, imagen gris 270x480)] repartidos por el clip, sin el primer ni el último segundo."""
    import numpy as np
    lo, hi = min(1.0, dur * 0.1), max(dur - 1.0, dur * 0.9)
    ts = [lo + (hi - lo) * i / max(1, n - 1) for i in range(n)]
    out = []
    for t in ts:
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-vf",
                            "scale=270:480,format=gray", "-f", "rawvideo", "-"], capture_output=True, timeout=60)
        if len(r.stdout) == 270 * 480:
            out.append((t, np.frombuffer(r.stdout, np.uint8).reshape(480, 270)))
    return out


def _sharp(g):
    import numpy as np
    g = g.astype(np.float32)
    lap = g[1:-1, 1:-1] * 4 - g[:-2, 1:-1] - g[2:, 1:-1] - g[1:-1, :-2] - g[1:-1, 2:]
    return float(lap.var())


def _duration(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                       capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def pick_time(video, rank=0):
    """Segundo del mejor cuadro. rank=1 da el mejor cuadro DISTINTO (a más de 20% del clip del primero), para la miniatura B."""
    dur = _duration(video)
    if dur < 3:
        return min(0.5, dur / 2)
    frames = _frames(video, dur)
    if not frames:
        return dur * 0.35
    try:
        import framing
        def face_of(g):
            fs = framing._detect(g, 0.08)
            f = max(fs, key=lambda f: f["w"]) if fs else None
            return (f["w"], f["x"]) if f else (None, None)
    except Exception:  # noqa: BLE001
        face_of = lambda g: (None, None)  # noqa: E731
    ranked = sorted(frames, key=lambda tg: -score_frame(_sharp(tg[1]), *face_of(tg[1]), float(tg[1].mean())))
    best = ranked[0][0]
    if rank <= 0:
        return best
    far = [tg for tg in ranked if abs(tg[0] - best) > dur * 0.2]
    return (far[0] if far else ranked[min(1, len(ranked) - 1)])[0]


def _font(size):
    from PIL import ImageFont
    for pat in FONTS:
        for p in glob.glob(pat, recursive=True):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def compose(frame, title, out, style=None):
    """Pone degradado y título (en mayúsculas, con la palabra más larga resaltada) sobre el cuadro. style = nombre de STYLES."""
    from PIL import Image, ImageDraw
    st = style_of(style)
    im = Image.open(frame).convert("RGB").resize((W, H))
    grad = Image.new("L", (1, H))
    for y in range(H):
        # la parte de abajo queda casi negra: así tapa los subtítulos que ya trae el cuadro y el título se lee siempre
        a = 0 if y < H * st["fade"] else int(252 * min(1.0, (y - H * st["fade"]) / (H * 0.14)))
        grad.putpixel((0, y), a)
    im.paste(Image.new("RGB", (W, H), (0, 0, 0)), (0, 0), grad.resize((W, H)))
    d = ImageDraw.Draw(im)
    text = " ".join(str(title or "").upper().split())[:70]
    size = 118
    font = _font(size)
    lines = _wrap(d, text, font, W - 160)
    while len(lines) > 4 and size > 70:
        size -= 8
        font = _font(size)
        lines = _wrap(d, text, font, W - 160)
    key = max(text.split(), key=len) if text else ""
    lh = int(size * 1.15)
    y = int(H * st["pos"])             # zona segura: arriba de la descripción y los botones de la red
    for ln in lines[:4]:
        x = (W - d.textlength(ln, font=font)) / 2
        for w in ln.split(" "):
            col = st["key"] if (st["key"] and w == key) else (255, 255, 255)
            d.text((x, y), w, font=font, fill=col, stroke_width=6, stroke_fill=(0, 0, 0))
            x += d.textlength(w + " ", font=font)
        y += lh
    im.save(out, "JPEG", quality=88)
    return Path(out)


def make_t(video, title, out, rank=0, at=None, style=None):
    """Como make, pero devuelve (ruta, segundo usado) para poder guardarlo. (None, None) si algo falla."""
    try:
        out = Path(out)
        if at is None:
            t = pick_time(video, rank)
        else:
            dur = _duration(video)
            t = max(0.0, min(float(at), max(0.0, dur - 0.1))) if dur else max(0.0, float(at))
        raw = out.with_suffix(".raw.jpg")
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(raw)],
                           capture_output=True, timeout=60)
        if r.returncode != 0 or not raw.exists():
            return None, None
        try:
            return compose(raw, title, out, style), round(float(t), 2)
        finally:
            raw.unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Miniatura: no pude ({type(e).__name__}: {str(e)[:100]})", flush=True)
        return None, None


def make(video, title, out, rank=0, at=None, style=None):
    """Miniatura del clip. at = segundo exacto del cuadro (si no, elige el mejor solo). Devuelve la ruta o None."""
    return make_t(video, title, out, rank, at, style)[0]
