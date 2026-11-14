"""Parte 4: un color de subtítulo por persona.

Necesita saber QUIÉN habla en cada momento (diarización). Eso lo hace pyannote.audio, que es opcional:
    pip install pyannote.audio       (trae PyTorch: pesa ~2 GB)
    HF_TOKEN=hf_...                  (llave gratis de huggingface.co y aceptar las condiciones del modelo pyannote/speaker-diarization-3.1)
Sin eso este módulo no hace nada y los subtítulos salen como siempre. Se analiza solo el tramo de cada clip.
"""
import subprocess
from pathlib import Path

import config

# Colores (RRGGBB) de la palabra activa. La persona 1 usa el color que elegiste en Ajustes; las demás, estos.
PALETTE = ["00D5FF", "FF4FD8", "7CFF4F", "FF9A3C"]
_pipe = None
_failed = False


def available():
    """True si pyannote está instalado, hay HF_TOKEN y no está apagado."""
    if config.SUBS_PER_SPEAKER in ("0", "false", "no", "off"):
        return False
    if not config.HF_TOKEN:
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("pyannote.audio") is not None
    except Exception:  # noqa: BLE001
        return False


def assign(words, turns, min_overlap=0.3):
    """Pone 'spk' (0, 1, 2…, en orden de aparición) a cada palabra según los turnos [(t0, t1, etiqueta)].
    Una palabra es de quien más tiempo la tenga hablando (si el solape es menor al 30 % de la palabra, queda sin etiqueta).
    Devuelve (palabras_nuevas, cuántas_personas)."""
    order = []
    out = []
    for w in words:
        dur = max(1e-6, w["end"] - w["start"])
        best, best_ov = None, 0.0
        for t0, t1, lab in turns:
            ov = min(w["end"], t1) - max(w["start"], t0)
            if ov > best_ov:
                best, best_ov = lab, ov
        if best is not None and best_ov / dur >= min_overlap:
            if best not in order:
                order.append(best)
            out.append({**w, "spk": order.index(best)})
        else:
            out.append(dict(w))
    return out, len(order)


def smooth(words, max_gap=0.8):
    """Una palabra suelta entre dos de la misma persona (error de la diarización) se corrige para que el color no parpadee."""
    ws = [dict(w) for w in words]
    for i in range(1, len(ws) - 1):
        a, b, c = ws[i - 1].get("spk"), ws[i].get("spk"), ws[i + 1].get("spk")
        if a is not None and a == c and b != a and ws[i + 1]["start"] - ws[i - 1]["end"] <= max_gap:
            ws[i]["spk"] = a
    return ws


def colors(n, active):
    """Color de cada persona (RRGGBB): la 0 con el color elegido por el usuario, el resto de la paleta sin repetir ese color."""
    pal = [c for c in PALETTE if c.upper() != str(active).lstrip("#").upper()]
    return [str(active).lstrip("#").upper()] + [pal[i % len(pal)] for i in range(max(0, n - 1))]


def _pipeline():
    global _pipe, _failed
    if _pipe is None and not _failed:
        try:
            from pyannote.audio import Pipeline
            try:
                _pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=config.HF_TOKEN)
            except TypeError:   # versiones 3.x usan use_auth_token
                _pipe = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=config.HF_TOKEN)
        except Exception as e:  # noqa: BLE001
            _failed = True
            print(f"  Subtítulos por persona: no pude cargar pyannote ({type(e).__name__}: {str(e)[:100]}).", flush=True)
    return _pipe


def diarize(source, start, end, workdir):
    """Turnos [(t0, t1, etiqueta)] en la línea de tiempo de `source`. Lista vacía si algo falla."""
    pipe = _pipeline()
    if pipe is None:
        return []
    wav = Path(workdir) / "spk.wav"
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{end - start:.2f}", "-i", str(source), "-vn",
                        "-ac", "1", "-ar", "16000", str(wav)], check=True, timeout=120)
        res = pipe(str(wav))
        diar = getattr(res, "speaker_diarization", res)     # pyannote 4 devuelve un objeto; 3.x, la anotación
        return [(start + t.start, start + t.end, lab) for t, _, lab in diar.itertracks(yield_label=True)]
    except Exception as e:  # noqa: BLE001
        print(f"  Subtítulos por persona: falló ({type(e).__name__}: {str(e)[:100]}).", flush=True)
        return []
    finally:
        wav.unlink(missing_ok=True)


def label_words(source, words, start, end, workdir):
    """Palabras del clip con 'spk' si hay 2 o más personas; si no, devuelve las palabras sin tocar. Siempre (palabras, n_personas)."""
    if not available():
        return words, 0
    inside = [w for w in words if w["start"] >= start - 0.05 and w["end"] <= end + 0.3]
    turns = diarize(source, start, end, workdir)
    if not turns:
        return words, 0
    lab, n = assign(inside, turns)
    if n < 2:
        return words, n
    lab = smooth(lab)
    ids = {(w["start"], w["end"], w["w"]): w.get("spk") for w in lab}
    return [{**w, "spk": ids[(w["start"], w["end"], w["w"])]} if (w["start"], w["end"], w["w"]) in ids and ids[(w["start"], w["end"], w["w"])] is not None else w
            for w in words], n
