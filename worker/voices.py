"""Parte 5: quién habla, sin instalar nada pesado.

Agrupa las frases de la transcripción por VOZ (timbre + tono) con numpy/scipy, que ya están instalados. No sabe nombres: reparte
"P1", "P2"... en orden de aparición. Sirve para:
  - decirle a la IA quién dice qué (la línea sale "[123] P2: ...") y detectar discusiones por cambios rápidos de persona,
  - subtítulos con un color por persona (render.py) sin pyannote.
Límites: separa voces que SUENAN distinto (hombre/mujer, graves/agudas). Dos voces muy parecidas se pueden mezclar, y la gente
que habla encima de otra no se separa (hay una etiqueta por frase). Si algo falla, devuelve sin tocar nada.
"""
import subprocess
from pathlib import Path

import config

RATE = 16000
FRAME = 512            # 32 ms
HOP = 256              # 16 ms
NMEL = 24
BLOCK_S = 60
MIN_VOICED = 25        # tramas con voz (~0.4 s) para poder opinar de una frase


def _mel_bank():
    import numpy as np
    def mel(f): return 2595 * np.log10(1 + f / 700.0)
    def inv(m): return 700 * (10 ** (m / 2595.0) - 1)
    pts = inv(np.linspace(mel(80), mel(7600), NMEL + 2))
    freqs = np.fft.rfftfreq(FRAME, 1.0 / RATE)
    bank = np.zeros((NMEL, len(freqs)), np.float32)
    for i in range(NMEL):
        lo, c, hi = pts[i], pts[i + 1], pts[i + 2]
        up = (freqs - lo) / (c - lo)
        dn = (hi - freqs) / (hi - c)
        bank[i] = np.clip(np.minimum(up, dn), 0, None)
    return bank


def frame_features(a, bank):
    """Por trama: (tiempo, vector mel logarítmico, f0 en Hz o 0, con_voz). a = audio mono float32 a 16 kHz."""
    import numpy as np
    n = (len(a) - FRAME) // HOP
    if n <= 0:
        return np.zeros(0), np.zeros((0, NMEL)), np.zeros(0), np.zeros(0, bool)
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n)[:, None]
    fr = a[idx]
    rms = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
    win = fr * np.hanning(FRAME).astype(np.float32)
    spec = np.abs(np.fft.rfft(win, axis=1)) ** 2
    logmel = np.log(spec @ bank.T + 1e-8)
    # tono por autocorrelación (70-400 Hz)
    ac = np.fft.irfft(np.abs(np.fft.rfft(fr - fr.mean(axis=1, keepdims=True), n=2 * FRAME, axis=1)) ** 2, axis=1)[:, :FRAME]
    lo, hi = int(RATE / 400), int(RATE / 70)
    seg = ac[:, lo:hi]
    k = seg.argmax(axis=1)
    strength = seg[np.arange(n), k] / (ac[:, 0] + 1e-9)
    f0 = RATE / (k + lo)
    thr = max(0.004, float(np.percentile(rms, 95)) * 0.12)   # relativo a lo fuerte del bloque (no a lo flojo: un bloque casi sin pausas se quedaba sin voz)
    voiced = (rms > thr) & (strength > 0.35)
    f0 = np.where(voiced, f0, 0.0)
    return (np.arange(n) * HOP / RATE), logmel.astype(np.float32), f0, voiced


def read_features(video, max_minutes=240):
    """Rasgos de todo el audio, leído por bloques. Devuelve (t, logmel, f0, voiced) o None si falla."""
    try:
        import numpy as np
        bank = _mel_bank()
        p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", str(RATE), "-t", str(max_minutes * 60),
                              "-f", "s16le", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except Exception:  # noqa: BLE001
        return None
    size = RATE * 2 * BLOCK_S
    T, M, F, V = [], [], [], []
    pos, carry = 0.0, np.zeros(0, np.float32)
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < FRAME * 2:
                break
            new = np.frombuffer(buf[: len(buf) // 2 * 2], np.int16).astype(np.float32) / 32768.0
            a = np.concatenate([carry, new])
            t, m, f, v = frame_features(a, bank)
            if len(t):
                T.append(t + pos - len(carry) / RATE); M.append(m); F.append(f); V.append(v)
            used = len(t) * HOP
            carry = a[used:]
            pos += len(new) / RATE
            if len(buf) < size:
                break
    except Exception:  # noqa: BLE001
        return None
    finally:
        try:
            p.stdout.close(); p.kill()
        except Exception:  # noqa: BLE001
            pass
    if not T:
        return None
    import numpy as np
    return np.concatenate(T), np.concatenate(M), np.concatenate(F), np.concatenate(V)


def segment_embeddings(segments, feats, shape=False):
    """Un vector por frase (media del mel en tramas con voz, menos la media global, + tono). None si la frase no tiene voz suficiente.
    shape=True (modo en vivo): en vez de restar la media global del trozo —que cambia de trozo a trozo— se resta la media entre bandas de la propia
    frase, así solo cuenta la forma del espectro y el volumen no mueve el vector."""
    import numpy as np
    t, m, f, v = feats
    gm = m[v].mean(axis=0) if v.any() else m.mean(axis=0)
    out = []
    for s in segments:
        i0, i1 = np.searchsorted(t, s["start"]), np.searchsorted(t, s["end"])
        vv = v[i0:i1]
        if vv.sum() < MIN_VOICED:
            out.append(None)
            continue
        mel = m[i0:i1][vv].mean(axis=0)
        mel = mel - (mel.mean() if shape else gm)
        pitch = float(np.median(f[i0:i1][vv & (f[i0:i1] > 0)]))
        out.append(np.concatenate([mel, [np.log2(pitch) * 6.0]]).astype(np.float32))   # 1 octava de tono pesa como el timbre
    return out


def cluster(embs, max_speakers=6, threshold=None):
    """Etiquetas 0..k-1 (None donde no hay vector), en orden de aparición. Agrupación jerárquica por promedio."""
    import numpy as np
    from scipy.cluster.hierarchy import fcluster, linkage
    idx = [i for i, e in enumerate(embs) if e is not None]
    out = [None] * len(embs)
    if len(idx) < 2:
        return [0 if e is not None else None for e in embs]
    X = np.stack([embs[i] for i in idx])
    thr = float(threshold if threshold is not None else config.VOICE_THRESHOLD)
    Z = linkage(X, "average", metric="euclidean")
    lab = fcluster(Z, t=thr * np.sqrt(X.shape[1]), criterion="distance")
    if len(set(lab)) > max_speakers:
        lab = fcluster(Z, t=max_speakers, criterion="maxclust")
    order = {}
    for l in lab:
        order.setdefault(int(l), len(order))
    for i, l in zip(idx, lab):
        out[i] = order[int(l)]
    return out


def _fill_gaps(labels, segments, max_gap=6.0):
    """Frases sin etiqueta (muy cortas) heredan la de la frase de al lado si está pegada, para que el color no desaparezca."""
    out = list(labels)
    for i, l in enumerate(out):
        if l is not None:
            continue
        prev = next((j for j in range(i - 1, -1, -1) if labels[j] is not None), None)
        nxt = next((j for j in range(i + 1, len(out)) if labels[j] is not None), None)
        cand = []
        if prev is not None and segments[i]["start"] - segments[prev]["end"] <= max_gap:
            cand.append(labels[prev])
        if nxt is not None and segments[nxt]["start"] - segments[i]["end"] <= max_gap:
            cand.append(labels[nxt])
        if cand and len(set(cand)) == 1:
            out[i] = cand[0]
    return out


def _apply(segments, words, labs):
    """Escribe las etiquetas: frases 'P1'.. y palabras 0.. (la palabra toma la frase donde empieza)."""
    import bisect
    for s, l in zip(segments, labs):
        if l is not None:
            s["spk"] = f"P{l + 1}"
    starts = [s["start"] for s in segments]
    for w in words:
        k = bisect.bisect_right(starts, w["start"] + 0.05) - 1
        if k >= 0 and labs[k] is not None and w["start"] <= segments[k]["end"] + 0.5:
            w["spk"] = labs[k]


class Tracker:
    """Modo en vivo: recuerda las voces ya oídas (una huella por persona) para que P1 siga siendo la misma persona en el trozo siguiente.
    Cada frase nueva se asigna a la huella más cercana, o crea una persona nueva si ninguna se parece (hasta VOICE_MAX)."""

    def __init__(self):
        self.cent = []      # [vector, cuántas frases]

    def label(self, path, segments, words, max_minutes=240):
        if not config.VOICES or not segments:
            return 0
        try:
            import numpy as np
            feats = read_features(path, max_minutes)
            if feats is None:
                return len(self.cent)
            embs = segment_embeddings(segments, feats, shape=True)
            thr = config.VOICE_THRESHOLD * np.sqrt(NMEL + 1)
            labs = []
            for e in embs:
                if e is None:
                    labs.append(None)
                    continue
                d = [float(np.linalg.norm(e - c[0])) for c in self.cent]
                k = int(np.argmin(d)) if d else -1
                if k < 0 or (d[k] > thr and len(self.cent) < config.VOICE_MAX):
                    self.cent.append([e.copy(), 1])
                    k = len(self.cent) - 1
                else:
                    c = self.cent[k]
                    c[0] = (c[0] * c[1] + e) / (c[1] + 1)
                    c[1] += 1
                labs.append(k)
            labs = _fill_gaps(labs, segments)
            _apply(segments, words, labs)
        except Exception as e:  # noqa: BLE001
            print(f"  Voces: no pude separarlas en este trozo ({type(e).__name__}: {str(e)[:100]})", flush=True)
        return len(self.cent)


def label(video, segments, words, max_minutes=240):
    """Pone seg['spk'] = 'P1'.. en las frases y w['spk'] = 0.. en las palabras (mismo orden). Devuelve cuántas personas oyó (0 = no se tocó nada)."""
    if not config.VOICES or not segments:
        return 0
    try:
        feats = read_features(video, max_minutes)
        if feats is None:
            return 0
        labs = _fill_gaps(cluster(segment_embeddings(segments, feats), config.VOICE_MAX), segments)
        n = len({l for l in labs if l is not None})
        if n < 2:
            return n
        _apply(segments, words, labs)
        return n
    except Exception as e:  # noqa: BLE001
        print(f"  Voces: no pude separarlas ({type(e).__name__}: {str(e)[:100]})", flush=True)
        return 0
