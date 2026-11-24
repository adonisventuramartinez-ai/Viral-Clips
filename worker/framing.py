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
from pathlib import Path

import config as _cfg

SAMPLE_FPS = _cfg.CLIP_CAM_FPS        # muestras por segundo para seguir la cámara
DET_W = _cfg.CLIP_CAM_DET_W          # ancho al que se reduce el cuadro para buscar caras
FACE_MIN = _cfg.CLIP_CAM_FACE_MIN     # cara mínima (fracción del ancho) en la segunda pasada
WIN = 3                              # +-3 muestras para decidir quién habla
MIN_DWELL = max(2, _cfg.CLIP_MIN_DWELL - 1)   # reacciona un poco más rápido
MIN_GAP = _cfg.CLIP_MIN_GAP
URGENT_EDGE = _cfg.CLIP_URGENT_EDGE
URGENT_DWELL = 2                     # muestras seguidas para ese caso
RAMP = max(0.3, _cfg.CLIP_RAMP - 0.1)   # paneo suave pero rápido
MIN_COVERAGE = _cfg.CLIP_MIN_COVERAGE

_det = None


_MODEL = "face_detection_yunet_2023mar.onnx"


def _cascade_dir():
    """Respaldo para OpenCV anterior a 5.x (que sí trae los .xml de Haar)."""
    local = Path(__file__).resolve().with_name("cascades")
    if (local / "haarcascade_frontalface_alt2.xml").exists():
        return str(local) + "/"
    try:
        import cv2
        d = cv2.data.haarcascades
        if (Path(d) / "haarcascade_frontalface_alt2.xml").exists():
            return d
    except Exception:  # noqa: BLE001
        pass
    return ""


def _load():
    """Detector YuNet (DNN de ~230 KB): ~50 ms por cuadro y ve caras de frente y de perfil.
    OpenCV 5.1 ya no expone CascadeClassifier y el respaldo scikit-image tardaba ~2.7 s por cuadro,
    así que el modelo va incluido en worker/cascades. Nunca lanza error: si falla, usa el respaldo."""
    global _det
    if _det is None:
        model = Path(__file__).resolve().with_name("cascades") / _MODEL
        if model.exists():
            try:
                import cv2
                det = cv2.FaceDetectorYN_create(str(model), "", (DET_W, DET_W // 2),
                                                score_threshold=0.55, nms_threshold=0.3, top_k=5000)
                if det is not None:
                    _det = ("yn", det)
                    return _det
            except Exception:  # noqa: BLE001
                pass
        try:
            import cv2
            d = _cascade_dir()
            if not d:
                raise RuntimeError("faltan los .xml de OpenCV (worker/cascades)")
            a = cv2.CascadeClassifier(d + "haarcascade_frontalface_alt2.xml")
            b = cv2.CascadeClassifier(d + "haarcascade_profileface.xml")
            c = cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml")
            if a.empty() or b.empty() or c.empty():
                raise RuntimeError("faltan los .xml de OpenCV")
            _det = ("cv2", a, b, c)
        except Exception:  # noqa: BLE001
            from skimage.data import lbp_frontal_face_cascade_filename
            from skimage.feature import Cascade
            _det = ("sk", Cascade(lbp_frontal_face_cascade_filename()), None)
    return _det


def _dedupe(boxes, overlap=0.45):
    """Quita cajas casi iguales: tres detectores ven la misma cara tres veces."""
    out = []
    for r in sorted(boxes, key=lambda z: -z[2] * z[3]):
        x, y, bw, bh = r
        area = max(1, bw * bh)
        dup = False
        for ox, oy, ow, oh in out:
            ix = max(0, min(x + bw, ox + ow) - max(x, ox))
            iy = max(0, min(y + bh, oy + oh) - max(y, oy))
            if ix * iy > overlap * min(area, ow * oh):
                dup = True
                break
        if not dup:
            out.append(r)
    return out


def _raw_boxes(gray, min_frac=None):
    """Lista de (x, y, w, h) en pixeles. min_frac = tamaño mínimo de la cara como fracción del ancho."""
    import numpy as np
    min_frac = FACE_MIN if min_frac is None else min_frac
    h, w = gray.shape
    det = _load()
    if det[0] == "yn":
        import cv2
        detector = det[1]
        detector.setInputSize((w, h))
        # YuNet espera BGR; el cuadro se lee en gris para el análisis de boca, lo convertimos aquí no más.
        bgr = cv2.cvtColor(np.ascontiguousarray(gray), cv2.COLOR_GRAY2BGR)
        _, faces = detector.detect(bgr)
        if faces is None:
            return []
        return [(float(f[0]), float(f[1]), float(f[2]), float(f[3])) for f in faces if float(f[14]) >= 0.5]
    if det[0] == "sk":
        raw = det[1].detect_multi_scale(gray, scale_factor=1.15, step_ratio=1,
                                        min_size=(max(12, int(w * min_frac * 0.9)),) * 2,
                                        max_size=(int(w * 0.4),) * 2)
        return [(r["c"], r["r"], r["width"], r["height"]) for r in raw]
    import cv2
    frontal, profile, frontal2 = det[1], det[2], det[3]
    g = np.ascontiguousarray(gray)
    # CLAHE suave: antes se usaba 8.0 y levantaba demasiado ruido en poca luz (falsas caras).
    g = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(g)
    g = cv2.medianBlur(g, 3)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    ms = (max(8, int(w * min_frac * 0.7)),) * 2

    def run(cascade, pic, neigh, flip_x=False):
        boxes = [tuple(r) for r in cascade.detectMultiScale(pic, 1.12, neigh, minSize=ms)]
        if flip_x:
            boxes = [(w - x - bw, y, bw, bh) for x, y, bw, bh in boxes]
        return boxes

    # Un solo detector frontal por cuadro: los otros tres se prueban SOLO si no vimos a nadie.
    # (Correr los 4 siempre costaba ~10x más y el directo se quedaba sin cámara a tiempo.)
    out = _dedupe(run(frontal, g, 4))
    if not out:
        out = _dedupe(run(frontal2, g, 3))
    if not out:
        flip = cv2.flip(g, 1)
        out = _dedupe(run(profile, g, 3) + run(profile, flip, 3, True))
    if not out:
        out = _dedupe(run(frontal, g, 2))
    return out


# ---------------------------------------------------------------- lectura y detección

def _read_frames(source, start, dur, src_w, src_h, det_w=DET_W, fps=SAMPLE_FPS):
    import numpy as np

    h = max(2, int(round(det_w * src_h / src_w / 2)) * 2)
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(source),
           "-vf", f"fps={fps},scale={det_w}:{h}:flags=lanczos,format=gray",
           "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    size = det_w * h
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            yield np.frombuffer(buf, np.uint8).reshape(h, det_w)
    finally:
        p.stdout.close()
        p.kill()
        p.wait()


def _detect(gray, min_frac=None):
    min_frac = FACE_MIN if min_frac is None else min_frac
    h, w = gray.shape
    faces = []
    for (x, y, bw, bh) in _raw_boxes(gray, min_frac):
        # Antes se descartaba todo lo que estuviera por debajo del 75% de altura: en los directos la gente está
        # sentada y se quedaba fuera del cuadro. Ahora se tolera hasta abajo del todo, pero se exige forma de cara.
        if y + bh * 0.5 > h * 0.92:
            continue
        ratio = bw / max(bh, 1)
        if not (0.55 <= ratio <= 1.6):
            continue
        if bw < max(10, w * min_frac * 0.55):
            continue
        if bw > w * 0.5 or bh < h * 0.018:
            continue
        faces.append({"x": (x + bw / 2) / w, "w": bw / w, "y": (y + bh / 2) / h, "box": (y, x, bw, bh)})
    # quita cajas repetidas (misma cara detectada por dos detectores distintos)
    out = []
    for f in sorted(faces, key=lambda f: -f["w"]):
        if all(abs(f["x"] - o["x"]) > max(f["w"], o["w"]) * 0.5 or abs(f["y"] - o["y"]) > max(f["w"], o["w"]) * 1.1 for o in out):
            out.append(f)
    return out


def _mouth_motion(prev, cur, box):
    """Movimiento de la BOCA, no de toda la cara: si se mueve la cabeza, se resta la frente de referencia."""
    import numpy as np

    r, c, bw, bh = box
    h, w = cur.shape
    x0, x1 = max(0, int(c + bw * 0.18)), min(w, int(c + bw * 0.82))
    y0, y1 = max(0, int(r + bh * 0.55)), min(h, int(r + bh * 0.92))
    f0, f1 = max(0, int(r + bh * 0.05)), min(h, int(r + bh * 0.35))
    if y1 <= y0 or x1 <= x0:
        return 0.0
    a = prev[y0:y1, x0:x1].astype(np.int16)
    b = cur[y0:y1, x0:x1].astype(np.int16)
    motion = float(np.abs(a - b).mean()) if a.size else 0.0
    if f1 > f0:
        aa = prev[f0:f1, x0:x1].astype(np.int16)
        bb = cur[f0:f1, x0:x1].astype(np.int16)
        if aa.size:
            motion = max(0.0, motion - 0.45 * float(np.abs(aa - bb).mean()))
    return motion


def sample_faces(source, start, dur, src_w, src_h, min_frac=None):
    samples, prev = [], None
    for i, gray in enumerate(_read_frames(source, start, dur, src_w, src_h)):
        faces = _detect(gray, min_frac)
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
    left = min(max(center - crop_frac / 2.0, 0.0), 1.0 - crop_frac)   # aún más centrado
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
        # varias caras lejos entre sí: gana quien mueve más la boca, dando más peso a los cuadros cercanos
        bins = {}
        for j in range(max(0, i - WIN), min(len(samples), i + WIN + 1)):
            wt = 1.0 / (1.0 + 0.5 * abs(j - i))
            for f in samples[j]["faces"]:
                b = bins.setdefault(round(f["x"] / 0.06), {"m": 0.0, "sx": 0.0, "wt": 0.0, "size": 0.0})
                b["m"] += f["m"] * wt
                b["sx"] += f["x"] * wt
                b["wt"] += wt
                b["size"] += f["w"] * wt
        best = max(bins.values(), key=lambda b: (b["m"], b["size"]))
        out.append(best["sx"] / best["wt"] if best["wt"] else out[-1])
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

    # mediana de 3 muestras + suavizado ligero: un cuadro suelto no mueve la cámara, pero tampoco va a saltos
    tg = [statistics.median(tg[max(0, i - 1): i + 2]) for i in range(len(tg))]
    sm = list(tg)
    for i in range(1, len(sm)):
        sm[i] = 0.65 * sm[i] + 0.35 * sm[i - 1]
    tg = sm

    dead = 0.07 * crop_frac   # zona muerta pequeña: sigue de cerca sin vibrar
    edge = URGENT_EDGE * crop_frac
    cur = statistics.median(tg[: max(3, int(SAMPLE_FPS * 2))])
    keys = [(0.0, _left(cur, crop_frac))]
    pending, urgent, since_move = 0, 0, -99.0
    for i, t in enumerate(tg):
        now = samples[i]["t"]
        pending = pending + 1 if abs(t - cur) > dead else 0
        urgent = urgent + 1 if abs(t - cur) > edge else 0   # la persona está casi fuera del cuadro
        go = pending >= MIN_DWELL or urgent >= URGENT_DWELL
        if go and now - since_move >= MIN_GAP:
            n = max(pending, urgent)
            new = statistics.median(tg[max(0, i - n + 1): i + 1])
            t0 = max(samples[max(0, i - n + 1)]["t"], keys[-1][0] + 0.05)
            keys.append((t0, keys[-1][1]))
            keys.append((t0 + RAMP, _left(new, crop_frac)))
            cur, pending, urgent, since_move = new, 0, 0, now
    if len(keys) == 1:   # nadie cambió: se queda quieto en la posición típica de todo el clip
        return [(0.0, _left(statistics.median(tg), crop_frac))]
    # sostené el último encuadre hasta el final para que no se corte a mitad de paneo
    keys.append((max(samples[-1]["t"] + 0.3, keys[-1][0] + 0.05), keys[-1][1]))
    return keys


# ---------------------------------------------------------------- API

def camera_keys(source, start, dur, src_w, src_h, crop_frac):
    """Claves de cámara para el clip, o None (usar centro). Nunca lanza error: si algo falla, centro."""
    try:
        samples = sample_faces(source, start, dur, src_w, src_h)
        keys = plan(samples, crop_frac)
        if keys is None:
            # Segunda pasada: caras más chicas (entrevista lejos, gorra, poca luz).
            samples = sample_faces(source, start, dur, src_w, src_h, min_frac=max(0.02, FACE_MIN * 0.75))
            keys = plan(samples, crop_frac)
            if keys:
                print("  Encuadre: la cara era pequeña, igual la seguí", flush=True)
        return keys
    except ImportError:
        print("  Encuadre: falta scikit-image, uso el centro (pip install scikit-image).", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Encuadre: no pude detectar caras ({type(e).__name__}: {str(e)[:100]}), uso el centro.", flush=True)
    return None


def x_expression(keys):
    """Claves [(t, fracción)] -> expresión de ffmpeg (en t) para la posición x del recorte: (iw-ow)*fracción."""
    def f(v):
        return f"{v:.4f}"

    def clamp(v):
        return f(min(1.0, max(0.0, v)))

    expr = clamp(keys[-1][1])
    for (t0, a), (t1, b) in reversed(list(zip(keys, keys[1:]))):
        seg = clamp(a) if abs(a - b) < 1e-6 else f"{clamp(a)}+({clamp(b - a)})*(t-{t0:.3f})/{max(t1 - t0, 0.05):.3f}"
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


# ---------------------------------------------------------------- cámara del streamer (facecam)
FACECAM_W = 960          # ancho de análisis (las caras de una cámara pequeña son diminutas)
FACECAM_SECS = 12.0
FACECAM_FPS = 2.0


def _in_corner(f):
    return (f["x"] < 0.42 or f["x"] > 0.58) and (f["y"] < 0.45 or f["y"] > 0.55)


def facecam_pick(samples, n_frames):
    """Lógica pura: de las caras vistas en varios cuadros saca la cara de la cámara del streamer (pequeña, en una esquina y
    siempre en el mismo sitio) o None. Una cara grande o en el centro es un video de charla, no una cámara sobre un juego."""
    cand = [f for s in samples for f in s if f["w"] <= 0.17 and _in_corner(f)]
    if len(cand) < max(3, 0.4 * n_frames):
        return None
    mx = statistics.median(f["x"] for f in cand)
    my = statistics.median(f["y"] for f in cand)
    mw = statistics.median(f["w"] for f in cand)
    same = [f for f in cand if abs(f["x"] - mx) <= max(0.03, mw * 0.8) and abs(f["y"] - my) <= max(0.05, mw * 1.2)]
    if len(same) < max(3, 0.4 * n_frames):
        return None
    # si en los mismos cuadros hay otra cara claramente más grande, la cámara es el contenido principal, no un recuadro
    for s in samples:
        if any(f["w"] > 0.22 for f in s):
            return None
    return {"x": statistics.median(f["x"] for f in same), "y": statistics.median(f["y"] for f in same),
            "w": statistics.median(f["w"] for f in same)}


def facecam_rect(stack, face):
    """Rectángulo (x0, y0, x1, y1) en fracciones del cuadro: el recuadro de la cámara.
    Primero busca la zona CONECTADA a la cara que casi no cambia entre cuadros (el juego se mueve; el marco de la cámara, no).
    Si esa zona no tiene forma de recuadro, estima uno alrededor de la cara (~2.8 veces el ancho de la cara) pegado al borde
    del video si la cara está cerca de él. stack = array (n, alto, ancho) en grises."""
    import numpy as np
    n, h, w = stack.shape
    fx, fy, fw = face["x"], face["y"], face["w"]
    rect = None
    try:
        import cv2
        std = stack.astype(np.float32).std(axis=0)
        thr = max(5.0, 0.6 * float(np.median(std)))
        mask = (std < thr).astype(np.uint8)
        k = max(3, int(w * 0.006)) | 1
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
        cnt, lab, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
        li = lab[min(h - 1, max(0, int(fy * h))), min(w - 1, max(0, int(fx * w)))]
        if li > 0:
            x, y, bw, bh, _a = stats[li]
            rw, rh = bw / w, bh / h
            ok = fw * 1.5 <= rw <= fw * 7 and rw * rh <= 0.35 and 0.5 <= bw / max(bh, 1) <= 3.0
            if ok:
                rect = (x / w, y / h, (x + bw) / w, (y + bh) / h)
    except ImportError:
        pass
    if rect is None:
        half_w = fw * 1.4
        half_h = half_w * (w / h) * 0.75
        x0, x1 = fx - half_w, fx + half_w
        y0, y1 = fy - half_h * 1.1, fy + half_h * 0.9
        if x0 < 0.06:
            x0 = 0.0
        if x1 > 0.94:
            x1 = 1.0
        if y0 < 0.06:
            y0 = 0.0
        if y1 > 0.94:
            y1 = 1.0
        rect = (max(0.0, x0), max(0.0, y0), min(1.0, x1), min(1.0, y1))
    return rect


def panel_in_rect(rect, face, src_w, src_h, aspect):
    """Recuadro (en % del video) con la proporción `aspect` (ancho/alto en pixeles), lo más grande posible DENTRO del recuadro de la
    cámara y centrado en la cara. Así el panel de arriba muestra solo al streamer, sin pedazos del juego."""
    x0, y0, x1, y1 = rect
    rw, rh = (x1 - x0) * src_w, (y1 - y0) * src_h
    bw = min(rw, rh * aspect)
    bh = bw / aspect
    cx = min(max(face["x"] * src_w, x0 * src_w + bw / 2), x1 * src_w - bw / 2)
    cy = min(max(face["y"] * src_h + bh * 0.05, y0 * src_h + bh / 2), y1 * src_h - bh / 2)
    return {"x": round((cx - bw / 2) / src_w * 100, 2), "y": round((cy - bh / 2) / src_h * 100, 2),
            "w": round(bw / src_w * 100, 2), "h": round(bh / src_h * 100, 2)}


def facecam_box(source, start, dur, src_w, src_h, aspect):
    """Recuadro (en % del video) de la cámara del streamer para el panel de arriba del modo dividido, o None si el video no tiene
    una cámara superpuesta (entonces se usa cam_box, que sigue la cara). Nunca lanza error."""
    try:
        import numpy as np
        frames, per = [], []
        for gray in _read_frames(source, start, min(dur, FACECAM_SECS), src_w, src_h, FACECAM_W, FACECAM_FPS):
            frames.append(gray)
            per.append(_detect(gray, 0.025))
        if len(frames) < 4:
            return None
        face = facecam_pick(per, len(frames))
        if not face:
            return None
        rect = facecam_rect(np.stack(frames), face)
        return panel_in_rect(rect, face, src_w, src_h, aspect)
    except ImportError:
        print("  Encuadre: falta numpy/scikit-image para buscar la cámara del streamer.", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Encuadre: no pude buscar la cámara del streamer ({type(e).__name__}: {str(e)[:100]}).", flush=True)
    return None
