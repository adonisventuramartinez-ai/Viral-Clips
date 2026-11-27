"""Pruebas de la Parte 5 (quién habla). Voces sintéticas generadas aquí, sin internet. Ejecuta: python test_parte5.py"""
import os
import tempfile
import wave
from collections import Counter
from pathlib import Path

import dotenv

dotenv.load_dotenv = lambda *a, **k: False
for k in list(os.environ):
    if k.startswith(("VOICE", "CLIP_", "SUBS_", "HF_")):
        del os.environ[k]

import numpy as np  # noqa: E402
from scipy.signal import lfilter  # noqa: E402

import analyze  # noqa: E402
import config  # noqa: E402
import detect  # noqa: E402
import profiles  # noqa: E402
import speakers  # noqa: E402
import voices  # noqa: E402

R = 16000
ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


def voice(f0, forms, dur, rng):
    n = int(dur * R); t = np.arange(n) / R
    f = f0 * (1 + 0.04 * np.sin(2 * np.pi * 3 * t + rng.random() * 6) + 0.01 * rng.normal(size=n).cumsum() / np.sqrt(n))
    src = (np.diff(np.floor(np.cumsum(f) / R), prepend=0) > 0).astype(np.float32)
    y = lfilter([1], [1, -0.97], src) + 0.02 * rng.normal(size=n)
    for fc, bw in forms:
        r = np.exp(-np.pi * bw / R); th = 2 * np.pi * fc / R
        y = lfilter([1 - r], [1, -2 * r * np.cos(th), r * r], y)
    y = y * (0.6 + 0.4 * np.sin(2 * np.pi * 4 * t) ** 2)
    return (y / np.abs(y).max() * 0.4).astype(np.float32)


V = {"A": (110, [(500, 80), (1500, 100), (2500, 150)]), "B": (210, [(750, 90), (1800, 110), (3000, 150)]),
     "C": (140, [(380, 70), (1000, 90), (2300, 140)])}


def build(order, seed=1):
    rng = np.random.default_rng(seed); parts, segs, t = [], [], 0.0
    for k in order:
        d = 2.5 + rng.random() * 2
        parts.append(voice(V[k][0], V[k][1], d, rng)); segs.append({"start": t, "end": t + d, "text": "x", "true": k}); t += d
        g = 0.5 + rng.random(); parts.append(0.002 * rng.normal(size=int(g * R)).astype(np.float32)); t += g
    return np.concatenate(parts), segs


def save(p, a):
    with wave.open(str(p), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(R); f.writeframes((a * 32767).astype(np.int16).tobytes())


tmp = Path(tempfile.mkdtemp())
order = list("BACABACCBAABCBACABCBAB")
a, segs = build(order)
save(tmp / "v.wav", a)

# 1) separa 3 voces distintas (el audio pasa de 60 s: también prueba la lectura por bloques)
E = voices.segment_embeddings(segs, voices.read_features(tmp / "v.wav"))
check("todas las frases tienen voz medible", all(e is not None for e in E))
lab = voices.cluster(E, 6)
m = {}
for l, s in zip(lab, segs):
    m.setdefault(l, Counter())[s["true"]] += 1
check("3 personas", len(m) == 3)
check("cada grupo es una sola voz", all(len(c) == 1 for c in m.values()))
check("orden de aparición: la primera voz es P1", lab[0] == 0)

# 2) label(): frases y palabras
words = [{"w": f"p{i}", "start": s["start"] + 0.2, "end": s["start"] + 0.5} for i, s in enumerate(segs)]
n = voices.label(tmp / "v.wav", segs, words)
check("label cuenta 3", n == 3)
check("frases con P1..P3", {s["spk"] for s in segs} == {"P1", "P2", "P3"} and segs[0]["spk"] == "P1")
check("palabras con índice", all(w["spk"] == int(s["spk"][1]) - 1 for w, s in zip(words, segs)))
check("la IA ve quién habla", " P2:" in analyze._line({**segs[1], "start": 3}))

# 3) una sola voz -> no etiqueta
a1, s1 = build(list("AAAAAA"), 2); save(tmp / "one.wav", a1)
w1 = [{"w": "x", "start": 0.3, "end": 0.6}]
check("una voz no se etiqueta", voices.label(tmp / "one.wav", s1, w1) < 2 and "spk" not in s1[0] and "spk" not in w1[0])

# 4) apagable
config.VOICES = False
s2 = [{k: v for k, v in s.items() if k != "spk"} for s in segs]   # copias sin las etiquetas del paso anterior
check("VOICES=0 no toca nada", voices.label(tmp / "v.wav", s2, [{"w": "x", "start": 0, "end": 1}]) == 0 and "spk" not in s2[0])
config.VOICES = True

# 5) frase corta sin voz suficiente hereda al vecino pegado
sg = [{"start": 0, "end": 3}, {"start": 3.1, "end": 3.4}, {"start": 3.5, "end": 6}]
check("hereda del vecino", voices._fill_gaps([0, None, 0], sg) == [0, 0, 0])
check("no inventa si los vecinos difieren", voices._fill_gaps([0, None, 1], sg) == [0, None, 1])

# 6) discusión por cambios de persona
lv = [60.0] * 10 + [70.0] * 25 + [60.0] * 25          # volumen alto sostenido 10-35 s (la mediana sigue siendo 60)
sw = [{"w": "x", "start": 10 + i * 0.8, "end": 10.5 + i * 0.8, "spk": i % 2} for i in range(30)]
nw = [{k: v for k, v in w.items() if k != "spk"} for w in sw]
check("turnos + volumen = discusión", len(detect.argument_from_signals(sw, lv)) > 0)
check("sin etiquetas de voz queda como antes (habla lenta, no cuenta)", len(detect.argument_from_signals(nw, lv)) == 0)
check("solo turnos, sin volumen: no", len(detect.argument_from_signals(sw, [60.0] * 50)) == 0)

# 7) subtítulos: colores consistentes con las voces ya etiquetadas
ws, nn = speakers.label_words("nada.mp4", words, segs[0]["start"], segs[5]["end"], tmp)
check("render usa las voces ya etiquetadas", nn >= 2)
check("perfiles con voces", all(profiles.get(p).get("voices") for p in ("reality", "podcast", "entrevista", "gta_rp", "directo"))
      and not profiles.get("gta").get("voices"))
print(f"OK: Parte 5, {ok} pruebas")
