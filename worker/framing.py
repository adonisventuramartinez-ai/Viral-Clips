"""Encuadre inteligente para clips verticales.

Mira el tramo del clip (3 cuadros por segundo), detecta las caras y decide qué parte del video horizontal
mostrar en el cuadro 9:16:
  - 1 persona          -> la sigue (sin mover la cámara por cada gesto).
  - 2+ cerca entre sí  -> las deja juntas.
  - 2+ lejos           -> va con quien habla (la cara con más movimiento de boca) y cambia con un paneo suave.
  - no encuentra caras -> centro (o CLIP_FOCUS_X).

Devuelve claves de cámara [(segundo, izquierda)] donde izquierda va de 0 a 1 (0 = recorte pegado al borde izquierdo,
1 = pegado al derecho). render.py las convierte en una expresión de ffmpeg.
"""
import statistics
import subprocess

SAMPLE_FPS = 3.0
DET_W = 640        # ancho al que se reduce el cuadro para buscar caras
WIN = 3            # +-1 s de ventana para decidir quién habla
MIN_DWELL = 4      # muestras seguidas (~1.3 s) antes de mover la cámara
MIN_GAP = 2.0      # segundos mínimos entre dos paneos
RAMP = 0.5         # duración del paneo
MIN_COVERAGE = 0.2  # si hay caras en menos de esta fracción del clip, se usa el centro

_cascade = None


def _load():
    global _cascade
    if _cascade is None:
        from skimage.data import lbp_frontal_face_cascade_filename
        from skimage.feature import Cascade

        _cascade = Cascade(lbp_frontal_face_cascade_filename())
    return _cascade


# ---------------------------------------------------------------- lectura y detección

def _read_frames(source, start, dur, src_w, src_h):
    import numpy as np

    h = max(2, int(round(DET_W * src_h / src_w / 2)) * 2)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(source),
           "-vf", f"fps={SAMPLE_FPS},scale={DET_W}:{h}:flags=bilinear,format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = DET_W * h
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, DET_W)
    finally:
        p.stdout.close()
        p.kill()
        p.wait()


def _detect(gray):
    h, w = gray.shape
    raw = _load().detect_multi_scale(gray, scale_factor=1.2, step_ratio=1,
                                     min_size=(int(w * 0.045),) * 2, max_size=(int(w * 0.4),) * 2)
    faces = []
    for r in raw:
        if r["r"] + r["height"] / 2 > h * 0.8:   # caras muy abajo suelen ser falsos positivos
            continue
        faces.append({"x": (r["c"] + r["width"] / 2) / w, "w": r["width"] / w,
                      "y": (r["r"] + r["height"] / 2) / h,
                      "box": (r["r"], r["c"], r["width"], r["height"])})
    # quita cajas repetidas (misma cara detectada dos veces)
    out = []
    for f in sorted(faces, key=lambda f: -f["w"]):
        if all(abs(f["x"] - o["x"]) > max(f["w"], o["w"]) * 0.6 or abs(f["y"] - o["y"]) > max(f["w"], o["w"]) * 1.2 for o in out):
            out.append(f)
    return out


def _mouth_motion(prev, cur, box):
    import numpy as np

    r, c, bw, bh = box
    y0, y1 = int(r + bh * 0.5), int(r + bh)
    x0, x1 = int(c), int(c + bw)
    a = prev[y0:y1, x0:x1].astype(np.int16)
    b = cur[y0:y1, x0:x1].astype(np.int16)
    return float(np.abs(a - b).mean()) if a.size else 0.0


def sample_faces(source, start, dur, src_w, src_h):
    samples, prev = [], None
    for i, gray in enumerate(_read_frames(source, start, dur, src_w, src_h)):
        faces = _detect(gray)
        for f in faces:
            f["m"] = _mouth_motion(prev, gray, f["box"]) if prev is not None else 0.0
            del f["box"]
        samples.append({"t": i / SAMPLE_FPS, "faces": faces})
        prev = gray
    return samples


# ---------------------------------------------------------------- decisión (lógica pura)

def _left(center, crop_frac):
    """Centro deseado (fracción del ancho) -> posición del recorte como fracción del ESPACIO SOBRANTE (0 = pegado a
    la izquierda, 1 = pegado a la derecha), que es lo que usa x=(iw-ow)*fracción en ffmpeg."""
    left = min(max(center - crop_frac / 2, 0.0), 1.0 - crop_frac)
    return left / (1.0 - crop_frac)


def _targets(samples, crop_frac):
    out = []
    for i, s in enumerate(samples):
        faces = s["faces"]
        if not faces:
            out.append(None)
            continue
        lo = min(f["x"] - f["w"] / 2 for f in faces)
        hi = max(f["x"] + f["w"] / 2 for f in faces)
        if len(faces) == 1 or hi - lo <= crop_frac * 0.92:
            out.append((lo + hi) / 2)
            continue
        # varias caras lejos entre sí: gana la zona con más movimiento de boca en +-1 s
        bins = {}
        for w in samples[max(0, i - WIN): i + WIN + 1]:
            for f in w["faces"]:
                b = bins.setdefault(round(f["x"] / 0.1), {"m": 0.0, "xs": [], "size": 0.0})
                b["m"] += f["m"]
                b["xs"].append(f["x"])
                b["size"] += f["w"]
        best = max(bins.values(), key=lambda b: (b["m"], b["size"]))
        out.append(sum(best["xs"]) / len(best["xs"]))
    return out


def plan(samples, crop_frac):
    """Devuelve claves [(t, izquierda 0-1)] o None si casi no hubo caras (usar centro)."""
    n = len(samples)
    if n == 0:
        return None
    tg = _targets(samples, crop_frac)
    known = [t for t in tg if t is not None]
    if len(known) / n < MIN_COVERAGE:
        return None
    # rellena huecos con el último valor conocido
    last = known[0]
    for i, t in enumerate(tg):
        if t is None:
            tg[i] = last
        else:
            last = t

    dead = 0.2 * crop_frac
    cur = statistics.median(tg[: max(3, int(SAMPLE_FPS * 2))])
    keys = [(0.0, _left(cur, crop_frac))]
    pending, since_move = 0, -99.0
    for i, t in enumerate(tg):
        now = samples[i]["t"]
        if abs(t - cur) > dead:
            pending += 1
        else:
            pending = 0
        if pending >= MIN_DWELL and now - since_move >= MIN_GAP:
            new = statistics.median(tg[i - pending + 1: i + 1])
            t0 = max(samples[i - pending + 1]["t"], keys[-1][0] + 0.1)   # el paneo empieza cuando empezó el cambio
            keys.append((t0, keys[-1][1]))
            keys.append((t0 + RAMP, _left(new, crop_frac)))
            cur, pending, since_move = new, 0, now
    if len(keys) == 1:   # nadie cambió: se queda quieto en la posición típica de todo el clip
        return [(0.0, _left(statistics.median(tg), crop_frac))]
    return keys


# ---------------------------------------------------------------- API

def camera_keys(source, start, dur, src_w, src_h, crop_frac):
    """Claves de cámara para el clip, o None (usar centro). Nunca lanza error: si algo falla, centro."""
    try:
        samples = sample_faces(source, start, dur, src_w, src_h)
        return plan(samples, crop_frac)
    except ImportError:
        print("  Encuadre: falta scikit-image, uso el centro (pip install scikit-image).", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Encuadre: no pude detectar caras ({type(e).__name__}: {str(e)[:100]}), uso el centro.", flush=True)
    return None


def x_expression(keys):
    """Claves [(t, fracción)] -> expresión de ffmpeg (en t) para la posición x del recorte: (iw-ow)*fracción."""
    def f(v):
        return f"{v:.4f}"

    expr = f(keys[-1][1])
    for (t0, a), (t1, b) in reversed(list(zip(keys, keys[1:]))):
        seg = f(a) if abs(a - b) < 1e-6 else f"{f(a)}+({f(b - a)})*(t-{t0:.3f})/{max(t1 - t0, 0.05):.3f}"
        expr = f"if(lt(t,{t1:.3f}),{seg},{expr})"
    return f"(iw-ow)*({expr})"


def cam_box(source, start, dur, src_w, src_h, aspect):
    """Recuadro (en % del video) alrededor de la cara más grande y constante, con la proporción `aspect` (ancho/alto).
    Sirve para el panel de la cámara en el modo dividido. Devuelve None si no hay cara fiable."""
    try:
        samples = sample_faces(source, start, min(dur, 12.0), src_w, src_h)
        faces = [f for s in samples for f in s["faces"]]
        if len(faces) < max(3, 0.15 * len(samples)):
            return None
        big = sorted(faces, key=lambda f: -f["w"])[: max(3, len(faces) // 2)]
        fx = statistics.median(f["x"] for f in big)
        fy = statistics.median(f["y"] for f in big)
        fw = statistics.median(f["w"] for f in big)
        w_pct = min(100.0, fw * 100 * 3.2)                      # la cara ocupa ~1/3 del panel
        h_pct = w_pct * src_w / (src_h * aspect)
        if h_pct > 100:
            h_pct = 100.0
            w_pct = h_pct * src_h * aspect / src_w
        x = min(max(fx * 100 - w_pct / 2, 0.0), 100 - w_pct)
        y = min(max(fy * 100 - h_pct * 0.45, 0.0), 100 - h_pct)   # cara un poco por encima del centro
        return {"x": round(x, 2), "y": round(y, 2), "w": round(w_pct, 2), "h": round(h_pct, 2)}
    except ImportError:
        print("  Encuadre: falta scikit-image (pip install scikit-image).", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Encuadre: no pude ubicar la cámara ({type(e).__name__}: {str(e)[:100]}).", flush=True)
    return None


def _panel_box(fx, fy, fw, src_w, src_h, aspect):
    """Recuadro (en % del video) centrado en una cara (fracciones 0-1) con la proporción `aspect`."""
    w_pct = min(100.0, fw * 100 * 3.2)
    h_pct = w_pct * src_w / (src_h * aspect)
    if h_pct > 100:
        h_pct = 100.0
        w_pct = h_pct * src_h * aspect / src_w
    x = min(max(fx * 100 - w_pct / 2, 0.0), 100 - w_pct)
    y = min(max(fy * 100 - h_pct * 0.45, 0.0), 100 - h_pct)
    return {"x": round(x, 2), "y": round(y, 2), "w": round(w_pct, 2), "h": round(h_pct, 2)}


def split_two(faces, n_samples, src_w, src_h):
    """Lógica pura: de todas las caras vistas saca (persona_de_arriba, persona_de_abajo) o None si no hay dos personas claras.
    Agrupa las caras en 2 grupos (k-means) y exige que estén bien separadas y presentes en suficientes cuadros.
    Orden: si están lado a lado, la de la izquierda va arriba; si una está sobre la otra, la de más arriba va arriba."""
    if len(faces) < 6 or n_samples < 3:
        return None
    k = src_h / src_w                                   # para medir distancias con la misma escala en x e y
    pts = [(f["x"], f["y"] * k, f["w"]) for f in faces]
    c = [min(pts, key=lambda p: p[0] + p[1]), max(pts, key=lambda p: p[0] + p[1])]
    c = [(p[0], p[1]) for p in c]
    groups = [[], []]
    for _ in range(12):
        groups = [[], []]
        for p in pts:
            d = [(p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in c]
            groups[0 if d[0] <= d[1] else 1].append(p)
        if not all(groups):
            return None
        c = [(statistics.median(p[0] for p in g), statistics.median(p[1] for p in g)) for g in groups]
    need = max(3, 0.15 * n_samples)
    if min(len(g) for g in groups) < need:
        return None
    sep = ((c[0][0] - c[1][0]) ** 2 + (c[0][1] - c[1][1]) ** 2) ** 0.5
    fw = statistics.median(p[2] for g in groups for p in g)
    if sep < max(0.18, fw * 1.8):                       # demasiado cerca: es una sola persona o dos pegadas
        return None
    people = [{"x": c[i][0], "y": c[i][1] / k, "w": statistics.median(p[2] for p in groups[i])} for i in range(2)]
    stacked = abs(c[0][1] - c[1][1]) > abs(c[0][0] - c[1][0])
    people.sort(key=lambda p: p["y"] if stacked else p["x"])
    return people[0], people[1]


def duo_boxes(source, start, dur, src_w, src_h, aspect):
    """Modo 'dos personas': devuelve (recuadro_arriba, recuadro_abajo) en % del video, o None si no ve a dos personas."""
    try:
        samples = sample_faces(source, start, min(dur, 15.0), src_w, src_h)
        faces = [f for s in samples for f in s["faces"]]
        two = split_two(faces, len(samples), src_w, src_h)
        if not two:
            return None
        return tuple(_panel_box(p["x"], p["y"], p["w"], src_w, src_h, aspect) for p in two)
    except ImportError:
        print("  Encuadre: falta scikit-image (pip install scikit-image).", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Encuadre: no pude ubicar a las dos personas ({type(e).__name__}: {str(e)[:100]}).", flush=True)
    return None
