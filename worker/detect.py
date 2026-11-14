"""Parte 3: detección mejorada.

- GTA: disparos y explosiones por AUDIO (💥), en lugar de depender de cambios de escena.
- GTA: pantallas de WASTED, BUSTED, MISSION PASSED y estrellas de policía, reconocidas por color y posición (📺). No lee letras
  (OCR): la tipografía de GTA lo hace poco fiable; la verificación con imágenes (vision.py) confirma lo dudoso.
- Reality: discusiones (volumen sostenido + mucha palabra por segundo + frases cortas seguidas + chat) (🗣️).
- Reality: filtro de clips repetidos (misma escena vista desde otra cámara) comparando lo que se dice.

Todo son ayudas opcionales: si algo falla devuelve vacío y el trabajo sigue igual.
Las funciones *_from_* son puras (reciben listas) para poder probarlas sin video.
"""
import re
import statistics
import subprocess
from pathlib import Path

import profiles

RATE = 16000          # Hz para el detector de impactos (los disparos tienen energía por encima de 4 kHz)
HOP = 160             # 10 ms por trama
FRAME = 320           # 20 ms de ventana


# ============================================================================= AUDIO: disparos y explosiones
def impact_features(a):
    """Por cada trama de 10 ms: (energía total dB, energía de graves <250 Hz dB, energía de agudos >3 kHz dB).
    Es lo único que hace falta para distinguir un disparo (seco, con agudos) de una explosión (grave y larga)."""
    import numpy as np
    n = (len(a) - FRAME) // HOP
    if n <= 0:
        return [], [], []
    win = np.hanning(FRAME).astype(np.float32)
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n)[:, None]
    fr = a[idx] * win
    spec = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    freqs = np.fft.rfftfreq(FRAME, 1.0 / RATE)
    tot = spec.sum(axis=1) + 1e-12
    low = spec[:, freqs < 250].sum(axis=1) + 1e-12
    high = spec[:, freqs > 3000].sum(axis=1) + 1e-12
    db = lambda x: (10 * np.log10(x)).tolist()  # noqa: E731
    return db(tot), db(low), db(high)


def impacts_from_features(tot, low, high, min_jump_db=14.0, min_abs_db=-48.0, lookahead=60):
    """Busca golpes de sonido: la energía sube de golpe (>= min_jump_db en 30 ms respecto a los 200 ms anteriores).
    Devuelve lista de (segundo_float, tipo) con tipo 'shot' (seco, con agudos, decae rápido) o 'boom' (grave y largo).
    Un golpe aislado de ruido normal (voz, música) no sube tanto tan rápido.
    lookahead = tramas (de 10 ms) que se necesitan después del golpe para juzgarlo (135 si el audio sigue, 60 si es el final)."""
    n = len(tot)
    out = []
    i = 25
    refractory = 0
    while i < n - lookahead:
        if i < refractory:
            i += 1
            continue
        base = statistics.fmean(tot[i - 25:i - 3])
        peak = max(tot[i:i + 3])
        if peak - base >= min_jump_db and peak >= min_abs_db:
            # a dónde llega la energía 60-400 ms después (decaimiento)
            tail_long = statistics.fmean(tot[i + 25:i + 45])      # ~250-450 ms
            tail_short = statistics.fmean(tot[i + 8:i + 14])      # ~80-140 ms
            lowness = statistics.fmean(low[i:i + 15]) - statistics.fmean(high[i:i + 15])   # >0 = más graves que agudos
            far = tot[i + 100:i + 130]       # ~1.0-1.3 s después: una explosión ya bajó, un grito o la música siguen igual de fuertes
            decays = (not far) or (statistics.fmean(far) - base <= 0.5 * (peak - base))
            sustained = tail_long - base >= 8.0 and lowness > 3.0 and peak - tail_long >= 4.0 and decays
            if sustained:
                kind = "boom"
            elif peak - tail_short >= 8.0 or tail_long - base < 6.0:
                kind = "shot"
            else:
                kind = None
            if kind:
                out.append((i * HOP / RATE, kind))
                refractory = i + (60 if kind == "boom" else 8)   # 600 ms (explosión) / 80 ms (disparo)
        i += 1
    return out


def combat_from_impacts(impacts, min_shots=3, burst_gap=2.0, boom_ok=True):
    """Pasa de golpes sueltos a SEGUNDOS de combate: ráfagas de >= min_shots disparos seguidos (cada uno a <= burst_gap s del
    anterior) o cualquier explosión. Devuelve (segundos_de_disparos, segundos_de_explosiones) como conjuntos de enteros."""
    shots = sorted(t for t, k in impacts if k == "shot")
    booms = sorted(t for t, k in impacts if k == "boom")
    shot_secs = set()
    cur = []
    for t in shots + [1e12]:
        if cur and t - cur[-1] > burst_gap:
            if len(cur) >= min_shots:
                shot_secs.update(range(int(cur[0]), int(cur[-1]) + 2))
            cur = []
        cur.append(t)
    boom_secs = {s for t in booms for s in (int(t), int(t) + 1)} if boom_ok else set()
    return shot_secs, boom_secs


BLOCK_S = 60          # segundos de audio que se analizan a la vez (así un VOD de 4 horas no llena la memoria)
PREFIX_S = 4          # segundos del bloque anterior que se repiten para no perder golpes en el borde
LOOK = 135            # tramas de 10 ms que hay que ver después de un golpe para decidir si fue explosión


def stream_impacts(video: Path, max_minutes=240):
    """Todos los golpes de sonido [(segundo, 'shot'|'boom')] del video, leyendo el audio por bloques. Lista vacía si falla."""
    try:
        import numpy as np
    except ImportError:
        return []
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(RATE), "-t", str(max_minutes * 60),
           "-f", "s16le", "-"]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        return []
    size = RATE * 2 * BLOCK_S
    carry = np.zeros(0, np.float32)
    pos = 0.0                      # segundo (absoluto) donde empieza el audio NUEVO de este bloque
    out = []
    try:
        buf = p.stdout.read(size)
        while len(buf) >= RATE:    # menos de 1 s de audio ya no sirve
            nxt = p.stdout.read(size) if len(buf) == size else b""
            final = not nxt
            new = np.frombuffer(buf[: len(buf) // 2 * 2], np.int16).astype(np.float32) / 32768.0
            win = np.concatenate([carry, new])
            win_start = pos - len(carry) / RATE
            found = impacts_from_features(*impact_features(win), lookahead=60 if final else LOOK)
            own_lo = 0.0 if pos == 0 else pos - LOOK * HOP / RATE          # lo anterior ya lo juzgó el bloque previo
            own_hi = float("inf") if final else pos + len(new) / RATE - LOOK * HOP / RATE
            out.extend((win_start + t, k) for t, k in found if own_lo <= win_start + t < own_hi)
            carry = win[-PREFIX_S * RATE:]
            pos += len(new) / RATE
            buf = nxt
    except Exception:  # noqa: BLE001
        return []
    finally:
        try:
            p.stdout.close()
            p.kill()
        except Exception:  # noqa: BLE001
            pass
    return out


def combat_seconds(video: Path, max_minutes=240):
    """(segundos con tiroteo, segundos con explosión) del video. Vacíos si falla."""
    try:
        return combat_from_impacts(stream_impacts(video, max_minutes))
    except Exception:  # noqa: BLE001
        return set(), set()


# ============================================================================= PANTALLA: WASTED / BUSTED / MISSION PASSED / estrellas
SCREEN_MARK = {"wasted": "WASTED", "busted": "BUSTED", "passed": "MISSION PASSED", "stars": "estrellas de policía"}


def classify_frame(bgr):
    """Clasifica UN fotograma de GTA 5 con color (rápido y sin internet). Devuelve 'wasted', 'busted', 'passed', 'stars' o None.

    - WASTED: toda la imagen casi sin color (blanco y negro) con letras ROJAS grandes en el centro.
    - BUSTED: igual, pero con letras AZULES.
    - MISSION PASSED: letras DORADAS/amarillas en el centro sobre imagen normal, con una franja horizontal delgada.
    - Estrellas: grupo de 3 a 5 manchas amarillas pequeñas en la esquina superior derecha (HUD de búsqueda).
    Son heurísticas: si no estás seguro, mejor devolver None (el modelo con visión confirma después)."""
    import cv2
    import numpy as np
    h, w = bgr.shape[:2]
    if h < 90 or w < 160:
        return None
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0].astype(np.int16), hsv[..., 1], hsv[..., 2]
    band = (slice(int(h * 0.38), int(h * 0.68)), slice(int(w * 0.12), int(w * 0.88)))   # franja central
    outside = np.ones((h, w), bool)
    outside[band] = False
    # color fuera de la franja central: ¿la escena está desaturada?
    sat_out = float(S[outside].mean())
    sat_band = S[band]
    hb, vb = H[band], V[band]
    strong = (sat_band > 120) & (vb > 70)
    red = strong & ((hb < 8) | (hb > 172))
    blue = strong & (hb > 100) & (hb < 130)
    gold = (sat_band > 110) & (vb > 150) & (hb > 15) & (hb < 35)
    area = float(sat_band.size)
    if sat_out < 45:
        if red.sum() / area > 0.012:
            return "wasted"
        if blue.sum() / area > 0.012:
            return "busted"
    # MISSION PASSED: dorado en el centro, repartido en horizontal (texto ancho y bajo), imagen con color normal
    if gold.sum() / area > 0.01 and sat_out >= 45:
        ys, xs = np.nonzero(gold)
        if len(xs) > 50 and (xs.max() - xs.min()) > 0.35 * w and (ys.max() - ys.min()) < 0.22 * h:
            return "passed"
    # Estrellas de búsqueda: esquina superior derecha
    corner = hsv[: int(h * 0.16), int(w * 0.70):]
    cs = (corner[..., 1] > 130) & (corner[..., 2] > 170) & (corner[..., 0] > 18) & (corner[..., 0] < 34)
    if 0.004 < cs.sum() / cs.size < 0.22:
        n, _lab, stats, _c = cv2.connectedComponentsWithStats(cs.astype(np.uint8), connectivity=8)
        blobs = [s for s in stats[1:] if 12 <= s[4] <= 1400]
        if 2 <= len(blobs) <= 6:
            ys = sorted(int(s[1]) for s in blobs)
            if ys[-1] - ys[0] <= 0.35 * corner.shape[0] + 6:    # alineadas en una fila
                return "stars"
    return None


def screen_events(video: Path, step=1.0, max_minutes=240):
    """Revisa 1 fotograma por segundo (pequeño, barato) y devuelve {segundo: tipo}. Vacío si falla.
    WASTED y BUSTED duran ~3-5 s: se exige verlos en 2 fotogramas seguidos para no confundir una sombra con la pantalla."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {}
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-an", "-t", str(max_minutes * 60),
           "-vf", f"fps={1.0 / step},scale=320:-2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    w = 320
    try:
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                "-of", "csv=p=0:s=x", str(video)], capture_output=True, text=True, timeout=60)
        iw, ih = [int(x) for x in probe.stdout.strip().split("x")[:2]]
        h = int(round(w * ih / iw / 2.0)) * 2
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        return {}
    labels = []
    size = w * h * 3
    while True:
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        labels.append(classify_frame(np.frombuffer(buf, np.uint8).reshape(h, w, 3)))
    p.stdout.close()
    p.wait()
    return confirm_events(labels, step)


def confirm_events(labels, step=1.0):
    """De la lista de etiquetas por fotograma a {segundo: tipo}: las pantallas finales (wasted/busted/passed) necesitan
    2 fotogramas seguidos del mismo tipo; las estrellas, 3 (el HUD parpadea cuando te buscan)."""
    need = {"wasted": 2, "busted": 2, "passed": 2, "stars": 3}
    out = {}
    run_t, run_n = None, 0
    for i, t in enumerate(list(labels) + [None]):
        if t is not None and t == run_t:
            run_n += 1
        else:
            if run_t and run_n >= need[run_t]:
                for j in range(i - run_n, i):
                    out[int(j * step)] = run_t
            run_t, run_n = t, 1 if t else 0
    return out


# ============================================================================= REALITY: discusiones
def argument_from_signals(words, levels, chat=None, lo=0, hi=None, win=8, min_wps=3.6, min_db_over=4.0):
    """Segundos (enteros) donde hay una DISCUSIÓN. Se exige que coincidan al menos 2 de estas 3 pistas en una ventana de `win` s:
      a) mucha palabra por segundo (>= min_wps: la gente habla rápido y encima de otra),
      b) volumen sostenido por encima de lo normal (no un pico suelto),
      c) el chat explotó (💬).
    Las palabras traen 'start'/'end' (segundos absolutos); levels[0] es el segundo `lo`. Sin diarización no se puede contar voces a la vez; esto es la mejor señal barata."""
    if not words or len(levels) < 20:
        return set()
    hi = int(hi if hi is not None else max(w["end"] for w in words) + 1)
    lo = int(lo)
    n = max(0, hi - lo)
    wps = [0] * n
    for w in words:
        k = int(w["start"]) - lo
        if 0 <= k < n:
            wps[k] += 1
    sm_lv = [statistics.fmean(levels[max(0, i - 1): i + 2]) for i in range(len(levels))]
    med = statistics.median(sm_lv)
    chat = chat or set()
    out = set()
    for a in range(lo, hi - win + 1, 2):
        rate = sum(wps[a - lo: a - lo + win]) / win
        vals = sm_lv[a - lo: a - lo + win] if a - lo >= 0 and a - lo + win <= len(sm_lv) else []
        loud_frac = (sum(1 for v in vals if v - med >= min_db_over) / len(vals)) if vals else 0.0
        a_ok = rate >= min_wps
        b_ok = loud_frac >= 0.6
        c_ok = sum(1 for t in range(a, a + win) if t in chat) >= win // 2
        if (a_ok + b_ok + c_ok) >= 2:
            out.update(range(a, a + win))
    return out


def argument_seconds(words, levels, chat=None, lo=0, hi=None):
    """Atajo seguro: nunca lanza error."""
    try:
        return argument_from_signals(words, levels, chat, lo, hi)
    except Exception:  # noqa: BLE001
        return set()


# ============================================================================= clips repetidos (otra cámara, mismo momento)
_STOP = set("de la que el en y a los se del las un por con no una su para es al lo como más pero sus le ya o este sí porque esta "
            "entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese "
            "eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa estos mucho quienes nada muchos cual "
            "poco ella estar estas algunas algo nosotros mi mis tú te ti tu tus ellas nosotras vosotros vosotras os mío mía".split())


def fingerprint(text, k=3):
    """Huella de lo que se dice: conjunto de grupos de k palabras (sin tildes, sin palabras vacías)."""
    toks = [t for t in re.findall(r"[a-z0-9ñ]+", profiles.norm(text)) if t not in _STOP and len(t) > 1]
    if len(toks) < k:
        return set(toks)
    return {" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)}


def similarity(fp_a, fp_b):
    """Qué tanto se parecen dos huellas (0..1): coincidencias / el más corto. Dos cámaras del mismo momento comparten casi todo."""
    if not fp_a or not fp_b:
        return 0.0
    return len(fp_a & fp_b) / max(1, min(len(fp_a), len(fp_b)))


def drop_repeats(moments, text_of, known=(), threshold=0.55):
    """Quita candidatos que cuentan lo mismo que uno ya elegido o ya publicado (otra cámara, mismo momento).
    - moments: lista de momentos YA ordenados de mejor a peor.
    - text_of(m): texto hablado del momento.
    - known: textos de clips ya creados antes (por ejemplo los últimos del mismo programa).
    Devuelve (conservados, descartados)."""
    kept, dropped = [], []
    fps = [fingerprint(t) for t in known]
    for m in moments:
        fp = fingerprint(text_of(m))
        if len(fp) >= 4 and any(similarity(fp, f) >= threshold for f in fps):
            dropped.append({"title": m["title"], "score": m["score"],
                            "reason": "Repetido: ya hay un clip que dice lo mismo (otra cámara o el mismo momento)"})
            continue
        kept.append(m)
        if len(fp) >= 4:
            fps.append(fp)
    return kept, dropped
