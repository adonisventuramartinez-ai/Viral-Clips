"""Pruebas de la Parte 6 (voces en vivo y opciones de la web). Voces sintéticas generadas aquí, sin internet. Ejecuta: python test_parte6.py"""
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
import re  # noqa: E402

import postfx  # noqa: E402

root = Path(__file__).resolve().parent.parent


def chunk(order, seed, gain=1.0):
    a, segs = build(order, seed)
    p = tmp / f"c{seed}.wav"
    save(p, a * gain)
    return p, segs


# 1) las mismas voces en dos trozos distintos (el segundo con menos volumen) conservan su número
tr = voices.Tracker()
p1, s1 = chunk(list("ABABCAB"), 11)
p2, s2 = chunk(list("CBACCAB"), 12, gain=0.4)
w1 = [{"w": "x", "start": s["start"] + 0.2, "end": s["start"] + 0.5} for s in s1]
n1 = tr.label(p1, s1, w1)
n2 = tr.label(p2, s2, [])
by = {}
for s in s1 + s2:
    by.setdefault(s["true"], set()).add(s.get("spk"))
check("3 personas en total", n2 == 3)
check("cada voz conserva su etiqueta entre trozos", all(len(v) == 1 and None not in v for v in by.values()))
check("voces distintas, etiquetas distintas", len({next(iter(v)) for v in by.values()}) == 3)
check("las palabras llevan el índice", all(w["spk"] == int(s["spk"][1]) - 1 for w, s in zip(w1, s1)))

# 2) un trozo sin voz o inexistente no rompe nada
check("trozo inexistente: no lanza error", tr.label(tmp / "no-existe.wav", [{"start": 0, "end": 3, "text": "x"}], []) == 3)
config.VOICES = False
check("VOICES=0: el rastreador no toca nada", voices.Tracker().label(p1, [dict(s) for s in s1], []) == 0)
config.VOICES = True

# 3) límite de personas
config.VOICE_MAX = 2
tr2 = voices.Tracker()
pp, ss = chunk(list("ABCABC"), 13)
tr2.label(pp, ss, [])
check("respeta VOICE_MAX", len({s["spk"] for s in ss if "spk" in s}) <= 2)
config.VOICE_MAX = 6

# 4) opciones de la web llegan al worker como "1" / "0" / "auto"
pr = profiles.get("podcast")
check('web "1" fuerza el zoom', postfx.wants(pr, {"zoom": "1"})[0] is True)
check('web "0" lo apaga', postfx.wants(profiles.get("gta"), {"zoom": "0", "slowmo": "0"}) == (False, False))
check('web "auto" deja decidir al perfil', postfx.wants(profiles.get("gta"), {"zoom": "auto", "slowmo": "auto"}) == (True, True))

# 5) la web manda y guarda esas opciones (prueba de texto: la web no se compila aquí)
route = (root / "app/api/jobs/route.ts").read_text(encoding="utf-8")
page = (root / "app/crear/page.tsx").read_text(encoding="utf-8")
for k in ("bleep", "loudnorm", "zoom", "slowmo"):
    check(f"ruta de trabajos acepta {k}", re.search(rf"\b{k}: tri\({k}\)", route) is not None)
    check(f"formulario ofrece {k}", f'["{k}",' in page)
check("el formulario envía las opciones", "progress_bar: bar, ...fx," in page)
check("las configuraciones guardadas incluyen las opciones", "bar, fx } }" in page and "setFx({ ...FX_DEFAULT, ...(p.fx ?? {}) })" in page)

# 6) GTA 6
g6 = profiles.get("gta6")
check("perfil gta6 existe y es de acción", g6["name"] == "gta6" and g6["action"] and g6["signals"] == {"combat": True} and g6["bonus"]["screen"] == 0)
check("gta6 usa zoom y cámara lenta", postfx.wants(g6) == (True, True))
for name, game in (("juego", "GTA 6"), ("gta", "Grand Theft Auto VI"), ("auto", "gta vi"), ("juego", "Leonida")):
    check(f"el juego '{game}' activa gta6", profiles.get(name, game)["name"] == "gta6")
for name, game in (("juego", "Valorant"), ("juego", "GTA 5"), ("gta", None), ("reality", "GTA 6")):
    check(f"'{name}' / {game}' NO activa gta6", profiles.get(name, game)["name"] != "gta6")
check("gta6 está en la lista de tipos", "gta6" in profiles.TYPES)
check("la guía de gta6 habla de GTA 6, no de GTA 5", "GTA 6" in g6["guide"] and "GTA 5" not in g6["guide"])
for f, needle in (("app/crear/page.tsx", '["gta6", "GTA 6 acción"]'), ("app/api/jobs/route.ts", '"gta6"'), ("app/api/watch/route.ts", '"gta6"'),
                  ("app/en-vivo/page.tsx", 'value="gta6"'), ("components/WatchChannels.tsx", 'gta6: "GTA 6 acción"')):
    check(f"web: {f} conoce gta6", needle in (root / f).read_text(encoding="utf-8"))
print(f"OK: Parte 6, {ok} pruebas")

# ---------------- GTA 6
import profiles as P  # noqa: E402

g6 = P.get("gta6")
check("perfil gta6 existe y es de acción", g6["name"] == "gta6" and g6["action"] and "GTA 6" in g6["label"])
check("gta6: zoom y cámara lenta, sin pantallas de GTA 5 sin calibrar",
      postfx.wants(g6) == (True, True) and not g6["signals"].get("screen") and g6["bonus"]["screen"] == 0 and g6["verify"])
check("gta6 está en la lista de tipos", "gta6" in P.TYPES)
for game in ("GTA 6", "gta VI", "Grand Theft Auto 6", "GTA6", "Vice City Leonida"):
    check(f"el juego '{game}' activa gta6", P.get("juego", game)["name"] == "gta6")
check("GTA 5 sigue siendo gta", P.get("juego", "GTA 5")["name"] == "juego" and P.get("gta", "GTA V online")["name"] == "gta")
check("GTA 6 RP no se mezcla con acción", P.get("juego", "GTA 6 RP")["name"] == "juego" and P.get("gta_rp", "GTA 6")["name"] == "gta_rp")
check("la IA recibe la guía de GTA 6", "Vice City" in analyze._build_prompt([{"start": 1, "end": 3, "text": "hola"}], 3, 25, g6, "GTA 6"))
for f, needle in (("app/api/jobs/route.ts", '"gta6"'), ("app/api/watch/route.ts", '"gta6"'), ("app/crear/page.tsx", '["gta6", "GTA 6 acción"]'),
                  ("app/en-vivo/page.tsx", 'value="gta6"'), ("components/WatchChannels.tsx", 'gta6: "GTA 6 acción"')):
    check(f"web: {f} ofrece gta6", needle in (root / f).read_text(encoding="utf-8"))
print(f"OK: Parte 6 (con GTA 6), {ok} pruebas")
