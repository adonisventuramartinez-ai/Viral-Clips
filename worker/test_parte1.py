"""Pruebas de la Parte 1 (sin red ni cupo): llaves de Groq, transcripción con varias llaves, empalme de trozos,
ventanas de análisis con solape. Ejecuta: python test_parte1.py"""
import os
import sys
import tempfile
import time
import types
from pathlib import Path

for k in list(os.environ):
    if k.startswith("GROQ") or k in ("CAST_NAMES", "WHISPER_PROMPT", "LLM_ORDER", "LLM_PROVIDER"):
        del os.environ[k]
os.environ["GROQ_KEYS_FILE"] = os.devnull

import config  # noqa: E402

# ---- 1) llaves: todas las formas, sin repetir
os.environ.update(GROQ_KEYS="gsk_a, gsk_b\ngsk_c", GROQ_API_KEY='"gsk_a",gsk_d', GROQ_API_KEY_7="gsk_e")
assert config.groq_keys() == ["gsk_a", "gsk_b", "gsk_c", "gsk_d", "gsk_e"], config.groq_keys()
tmp = Path(tempfile.mkdtemp()) / "k.txt"
tmp.write_text("# mis cuentas\ngsk_f\n\ngsk_a  # repetida\ngsk_g\n", encoding="utf-8")
os.environ["GROQ_KEYS_FILE"] = str(tmp)
assert config.groq_keys()[-2:] == ["gsk_f", "gsk_g"] and len(config.groq_keys()) == 7
os.environ["GROQ_KEYS_FILE"] = os.devnull

# ---- 2) prompt de Whisper con elenco
os.environ["CAST_NAMES"] = "Maria, Pedro"
import importlib  # noqa: E402
importlib.reload(config)
p = config.whisper_prompt()
assert "Alofoke" in p and "Maria" in p and "Pedro" in p and len(p) <= 700, p

import transcribe  # noqa: E402

# ---- 3) rotación en la transcripción: 429 en la llave 1 -> usa la llave 2 (antes se rendía)
sent = []


class R:
    def __init__(self, status, body=None, headers=None, text=""):
        self.status_code, self._b, self.headers, self.text = status, body or {}, headers or {}, text
        self.ok = 200 <= status < 300

    def json(self):
        return self._b


def fake_post(url, headers=None, files=None, data=None, timeout=None):
    key = headers["Authorization"].split()[-1]
    sent.append((key, dict(data) if not isinstance(data, list) else dict(data)))
    if key in ("gsk_a", "gsk_b"):
        return R(429, headers={"retry-after": "3000"}, text="audio seconds per day")
    return R(200, {"segments": [], "words": []})


sys.modules["requests"] = types.SimpleNamespace(post=fake_post, RequestException=OSError)
os.environ["GROQ_KEYS"] = "gsk_a,gsk_b,gsk_c"
os.environ.pop("GROQ_API_KEY_7", None); os.environ["GROQ_API_KEY"] = ""
mp3 = Path(tempfile.mkdtemp()) / "c.mp3"
mp3.write_bytes(b"x")
transcribe._key_cool.clear(); transcribe._key_dead.clear()
transcribe._post_with_keys(mp3, config.groq_keys())
assert [k for k, _ in sent] == ["gsk_a", "gsk_b", "gsk_c"], sent
assert "prompt" in sent[-1][1] and "Alofoke" in sent[-1][1]["prompt"]
assert transcribe._key_cool["gsk_a"] - time.time() > 600          # descansa mucho rato

# la siguiente vez ni toca las que no tienen cupo
sent.clear()
transcribe._post_with_keys(mp3, config.groq_keys())
assert [k for k, _ in sent] == ["gsk_c"], sent

# todas sin cupo (y espera larga) -> avisa para usar Whisper local
transcribe._key_cool.update({k: time.time() + 3000 for k in "gsk_a gsk_b gsk_c".split()})
try:
    transcribe._post_with_keys(mp3, config.groq_keys())
    raise SystemExit("debió fallar")
except transcribe._UseLocal as e:
    assert "sin cupo" in str(e), e

# todas rechazadas (401) -> también plan B
transcribe._key_cool.clear()
sys.modules["requests"].post = lambda *a, **k: R(401, text="bad")
try:
    transcribe._post_with_keys(mp3, config.groq_keys())
    raise SystemExit("debió fallar")
except transcribe._UseLocal:
    pass
assert transcribe._key_dead == {"gsk_a", "gsk_b", "gsk_c"}

# ---- 4) empalme de trozos: una palabra en la frontera sale UNA vez y completa
# Audio simulado de 25 s con trozos de 10 s y 2 s de margen. Palabras cada 1 s: w0..w24 (start=i, end=i+0.8)
transcribe._key_cool.clear(); transcribe._key_dead.clear()
config.TRANSCRIBE_CHUNK, config.TRANSCRIBE_PAD = 10, 2
transcribe._duration = lambda v: 25.0
ffmpeg_calls = []


def fake_run(cmd):
    ffmpeg_calls.append((float(cmd[cmd.index("-ss") + 1]), float(cmd[cmd.index("-t") + 1])))


transcribe._run = fake_run
cur = {}


def fake_post_keys(mp3p, keys):
    ss, ln = ffmpeg_calls[-1]
    words = [{"word": f"w{i}", "start": i - ss, "end": i + 0.8 - ss} for i in range(25) if ss <= i < ss + ln]
    segs = [{"start": i - ss, "end": i + 3 - ss, "text": f"s{i}"} for i in range(0, 25, 3) if ss <= i < ss + ln]
    return R(200, {"segments": segs, "words": words})


transcribe._post_with_keys = fake_post_keys
wd = Path(tempfile.mkdtemp())
segs, words = transcribe._groq(Path("x.mp4"), wd, ["gsk_a"])
assert [w["w"] for w in words] == [f"w{i}" for i in range(25)], [w["w"] for w in words]       # ni faltan ni se repiten
assert all(abs(w["start"] - int(w["w"][1:])) < 1e-6 for w in words)                          # tiempos absolutos bien
assert [s["text"] for s in segs] == [f"s{i}" for i in range(0, 25, 3)], [s["text"] for s in segs]
assert ffmpeg_calls[0][0] == 0 and ffmpeg_calls[1][0] == 8 and ffmpeg_calls[2][0] == 18, ffmpeg_calls   # arranca 2 s antes

# ---- 5) ventanas de análisis con solape
os.environ["GROQ_API_KEY"] = "gsk_x"
import analyze  # noqa: E402

segs = [{"start": i * 10.0, "end": i * 10.0 + 9, "text": "x"} for i in range(400)]   # 4000 s
ch = analyze._chunks(segs)
assert len(ch) >= 4
seen = set()
for a, b in zip(ch, ch[1:]):
    over = a[-1]["end"] - b[0]["start"]
    assert 80 <= over <= 100, over                   # ~90 s de solape
    seen |= {s["start"] for s in a}
seen |= {s["start"] for s in ch[-1]}
assert seen == {s["start"] for s in segs}, "se perdió algún segmento"
assert analyze._chunks([]) == [] and len(analyze._chunks(segs[:5])) == 1

# un momento en el borde (840-930 s) cabe completo en alguna ventana
assert any(c[0]["start"] <= 840 and c[-1]["end"] >= 930 for c in ch)
print("OK: pruebas de la Parte 1 pasaron")
