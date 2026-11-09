"""Pruebas del encuadre inteligente y del render nítido. Ejecuta: python test_framing.py"""
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import config
import framing
import render

CROP = 0.3158  # 9/16 de un video 16:9
FPS = framing.SAMPLE_FPS


def samples(spec, n):
    """spec(i) -> lista de (x, w, movimiento)."""
    return [{"t": i / FPS, "faces": [{"x": x, "w": w, "m": m} for x, w, m in spec(i)]} for i in range(n)]


# 1) una persona a la izquierda: cámara quieta, pegada a ella
k = framing.plan(samples(lambda i: [(0.25 + 0.01 * (i % 3), 0.08, 1)], 90), CROP)
assert len(k) == 1 and abs(k[0][1] - (0.26 - CROP / 2) / (1 - CROP)) < 0.05, k

# 2) dos personas cerca (caben en el cuadro): se quedan juntas
k = framing.plan(samples(lambda i: [(0.45, 0.07, 1), (0.55, 0.07, 3)], 90), CROP)
assert len(k) == 1 and abs(k[0][1] * (1 - CROP) + CROP / 2 - 0.5) < 0.03, k

# 3) dos lejos, habla primero la izquierda (0-10 s) y luego la derecha (10-20 s): hace UN paneo cerca de los 10 s
def two(i):
    left_talks = i < 30
    return [(0.2, 0.08, 6 if left_talks else 0.3), (0.8, 0.08, 0.3 if left_talks else 6)]
k = framing.plan(samples(two, 60), CROP)
assert abs(k[0][1] - (0.2 - CROP / 2) / (1 - CROP)) < 0.07, k
assert abs(k[-1][1] - (0.8 - CROP / 2) / (1 - CROP)) < 0.07, k
pan_start = k[1][0]
assert 8.0 < pan_start < 11.0, k
assert len(k) == 3, k   # mantiene, empieza paneo, llega

# 4) un solo "falso" ruido de un cuadro no mueve la cámara
def blip(i):
    return [(0.25, 0.08, 1)] if i != 20 else [(0.8, 0.08, 1)]
k = framing.plan(samples(blip, 60), CROP)
assert len(k) == 1, k

# 5) sin caras -> None (usar centro)
assert framing.plan(samples(lambda i: [], 60), CROP) is None

# 6) el recorte nunca se sale del cuadro
k = framing.plan(samples(lambda i: [(0.98, 0.06, 1)], 60), CROP)
assert abs(k[0][1] - 1.0) < 1e-9, k
print("OK: lógica de encuadre (6 pruebas)")

# ---------------- render real con ffmpeg ----------------
tmp = Path(tempfile.mkdtemp())
src = tmp / "src.mp4"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=3840x2160:rate=25",
                "-f", "lavfi", "-i", "sine=frequency=440", "-t", "6", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
assert render._probe(src) == (3840, 2160)

# expresión con paneo: izquierda al inicio, derecha al final
keys = [(0.0, 0.0), (2.0, 0.0), (2.5, 1.0)]
expr = framing.x_expression(keys)
config.CLIP_FRAMING = "center"
orig = framing.camera_keys
framing.camera_keys = lambda *a, **k: keys
config.CLIP_FRAMING = "auto"
out = tmp / "o.mp4"
render.render_clip(src, [{"w": "hola", "start": 0.2, "end": 0.8}], 0.0, 5.0, out, tmp)
info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                       "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout.strip()
assert info == "1080,1920", info


def frame(t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", "-vf", "scale=54:96",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(96, 54, 3).astype(int)


a, b = frame(0.5), frame(4.5)
assert np.abs(a - b).mean() > 10, "la cámara no se movió"
print("OK: render 4K -> 1080x1920 con paneo (", round(out.stat().st_size / 1e6, 1), "MB )")
framing.camera_keys = orig

# tope de tamaño: clip de 81 s no pasa de ~44 MB
assert render._bitrate(81) * 81 / 8 < 46e6 and render._bitrate(20) == 12_000_000
print("OK: bitrate dinámico")

# ---------------- detección real de caras (astronauta de scikit-image) ----------------
from PIL import Image  # noqa: E402
from skimage import data  # noqa: E402

astro = Image.fromarray(data.astronaut())


def make_video(path, placer, secs=4, fps=6):
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080",
                          "-r", str(fps), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "12", str(path)],
                         stdin=subprocess.PIPE)
    for i in range(secs * fps):
        canvas = Image.new("RGB", (1920, 1080), (90, 90, 90))
        placer(canvas, i / fps)
        p.stdin.write(canvas.tobytes())
    p.stdin.close()
    p.wait()


def paste(canvas, x, size=900):
    canvas.paste(astro.resize((size, size)), (x, 90))


# una persona a la izquierda (cara en ~x=0.26) y otra video con la persona a la derecha (~x=0.74)
make_video(tmp / "izq.mp4", lambda c, t: paste(c, 100))
make_video(tmp / "der.mp4", lambda c, t: paste(c, 920))
ki = framing.camera_keys(tmp / "izq.mp4", 0, 4, 1920, 1080, CROP)
kd = framing.camera_keys(tmp / "der.mp4", 0, 4, 1920, 1080, CROP)
print("claves izq:", ki, " der:", kd)
assert ki and kd, "no detectó la cara"
assert ki[0][1] < 0.3 and kd[-1][1] > 0.7, (ki, kd)
print("OK: detecta la cara y mueve el encuadre hacia ella")

# dos personas lejos; solo la de la derecha mueve la boca -> debe irse con la derecha
def dos(c, t):
    paste(c, 40, 700)
    right = astro.resize((700, 700)).copy()
    arr = np.array(right)
    if int(t * 3) % 2:  # parpadeo en la zona de la boca (visible a 3 muestras por segundo)
        arr[150:240, 230:400] = np.clip(arr[150:240, 230:400].astype(int) + 60, 0, 255)
    c.paste(Image.fromarray(arr.astype(np.uint8)), (1180, 190))


make_video(tmp / "dos.mp4", dos, secs=6)
kk = framing.camera_keys(tmp / "dos.mp4", 0, 6, 1920, 1080, CROP)
print("claves dos personas:", kk)
assert kk and kk[-1][1] > 0.7, kk
print("OK: con dos personas sigue a la que se mueve")

# la cara debe quedar COMPLETA dentro del cuadro final (se mide en el video ya renderizado)
for nombre, lado in (("izq.mp4", "izq"), ("der.mp4", "der")):
    out2 = tmp / f"final_{lado}.mp4"
    render.render_clip(tmp / nombre, [], 0.0, 3.0, out2, tmp)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", str(out2), "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    g = np.frombuffer(raw, np.uint8).reshape(1920, 1080)
    import framing as F
    F._load()
    small = g[::2, ::2]
    det = F._load().detect_multi_scale(small, scale_factor=1.2, step_ratio=1, min_size=(60, 60), max_size=(500, 500))
    assert det, f"no se ve la cara completa en el clip final ({lado})"
    cx = (det[0]["c"] + det[0]["width"] / 2) / small.shape[1]
    assert 0.2 < cx < 0.8, (lado, cx)
print("OK: la cara sale completa y centrada en el clip final")
