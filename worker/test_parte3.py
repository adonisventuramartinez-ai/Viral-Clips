"""Pruebas de la Parte 3 (detección mejorada). No usa internet ni cupo de IA. Ejecuta: python test_parte3.py"""
import os
import sys
import types
import wave

import dotenv

dotenv.load_dotenv = lambda *a, **k: False      # la prueba no debe leer tu worker/.env real
for k in list(os.environ):
    if k.endswith("_API_KEY") or k.startswith("GROQ_") or k in ("LLM_ORDER", "LLM_PROVIDER", "VERIFY_IMAGES"):
        del os.environ[k]
os.environ.update(GROQ_API_KEY="gsk_x", GROQ_KEYS_FILE=os.devnull, LLM_MAX_WAIT="2")

import numpy as np  # noqa: E402
import cv2  # noqa: E402

import analyze  # noqa: E402
import config  # noqa: E402
import detect  # noqa: E402
import energy  # noqa: E402
import llm  # noqa: E402
import profiles  # noqa: E402
import vision  # noqa: E402

R = detect.RATE
ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


# ----------------------------------------------------------------- 1) audio: disparos y explosiones
rng = np.random.default_rng(1)
T = 40
t = np.arange(R * T) / R
bg = np.convolve(rng.normal(0, 1, len(t)), np.ones(8) / 8, "same").astype(np.float32) * 0.04 * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
a = bg.copy()


def shot(at, amp=0.7):
    n = int(0.06 * R); i = int(at * R)
    a[i:i + n] += (rng.normal(0, 1, n) * np.exp(-np.arange(n) / (0.012 * R)) * amp).astype(np.float32)


def boom(at, amp=0.8):
    n = int(1.2 * R); i = int(at * R)
    x = np.convolve(rng.normal(0, 1, n), np.ones(40) / 40, "same") * 6
    a[i:i + n] += (x * np.exp(-np.arange(n) / (0.35 * R)) * amp).astype(np.float32)


for s_ in (10.0, 10.25, 10.5, 10.8):
    shot(s_)
shot(25.0)                  # un disparo suelto no es tiroteo
boom(32.0)
seg = slice(R * 18, R * 20)  # un grito sostenido NO es explosión
a[seg] += (np.sin(2 * np.pi * 220 * t[seg]) * 0.3 * (0.5 + 0.5 * np.sin(2 * np.pi * 5 * t[seg]))).astype(np.float32)
a = np.clip(a, -1, 1)
imp = detect.impacts_from_features(*detect.impact_features(a))
shots, booms = detect.combat_from_impacts(imp)
check("ráfaga de 4 disparos detectada", {9, 10, 11} <= shots)
check("disparo suelto no cuenta", 25 not in shots and 24 not in shots)
check("explosión detectada", 31 in booms or 32 in booms)
check("grito sostenido no es explosión", not ({17, 18, 19} & booms))
check("solo ruido de fondo = nada", detect.impacts_from_features(*detect.impact_features(bg)) == [])

wav = "/tmp/_p3.wav"
with wave.open(wav, "wb") as w:      # y también leyendo un archivo real con ffmpeg
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(R)
    w.writeframes((a * 32767).astype(np.int16).tobytes())
from pathlib import Path  # noqa: E402
sh2, bo2 = detect.combat_seconds(Path(wav))
check("combat_seconds sobre un archivo", {9, 10, 11} <= sh2 and (31 in bo2 or 32 in bo2))
# audio de 150 s con una ráfaga que cruza el borde de bloque (60 s) y una explosión justo en el otro borde (120 s)
T2 = 150
rg = np.random.default_rng(7)
a2 = np.convolve(rg.normal(0, 1, R * T2), np.ones(8) / 8, "same").astype(np.float32) * 0.03


def put(sig, at):
    i = int(at * R); a2[i:i + len(sig)] += sig.astype(np.float32)


for at in (58.9, 59.2, 59.5, 59.8, 60.1, 60.4):
    n_ = int(0.06 * R); put(rg.normal(0, 1, n_) * np.exp(-np.arange(n_) / (0.012 * R)) * 0.7, at)
n_ = int(1.2 * R); put(np.convolve(rg.normal(0, 1, n_), np.ones(40) / 40, "same") * 6 * np.exp(-np.arange(n_) / (0.35 * R)) * 0.8, 119.5)
wav2 = "/tmp/_p3_long.wav"
with wave.open(wav2, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(R)
    w.writeframes((np.clip(a2, -1, 1) * 32767).astype(np.int16).tobytes())
imp2 = detect.stream_impacts(Path(wav2))
check("audio largo: los 6 disparos del borde salen una sola vez", sum(1 for _t, k in imp2 if k == "shot") == 6)
check("audio largo: la explosión del borde sale una sola vez", sum(1 for _t, k in imp2 if k == "boom") == 1)
sh3, bo3 = detect.combat_seconds(Path(wav2))
check("audio largo: tiroteo y explosión en los segundos correctos", {59, 60} <= sh3 and (119 in bo3 or 120 in bo3))
check("archivo que no existe = vacío, sin error", detect.combat_seconds(Path("/tmp/no_existe.mp4")) == (set(), set()))

# ----------------------------------------------------------------- 2) pantalla
H, W = 180, 320


def scene(seed, gray=False):
    r = np.random.default_rng(seed)
    hsv = np.zeros((H, W, 3), np.uint8)
    hsv[..., 0] = r.integers(0, 3, (H, W)) * 0
    hsv[:, : W // 3, 0] = 100; hsv[:, W // 3: 2 * W // 3, 0] = 60; hsv[:, 2 * W // 3:, 0] = 5
    hsv[..., 1], hsv[..., 2] = 150, 150
    img = cv2.GaussianBlur(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), (0, 0), 3)
    if gray:
        img = cv2.cvtColor(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    return img


def txt(img, s_, color, scale=1.6):
    cv2.putText(img, s_, (30, 100), cv2.FONT_HERSHEY_DUPLEX, scale, color, 3, cv2.LINE_AA)
    return img


stars = scene(4)
for i in range(4):
    cv2.circle(stars, (W - 70 + i * 16, 14), 5, (30, 220, 250), -1)
red_car = scene(6)
cv2.rectangle(red_car, (120, 80), (200, 120), (30, 30, 210), -1)
check("WASTED", detect.classify_frame(txt(scene(1, True), "wasted", (30, 30, 200))) == "wasted")
check("BUSTED", detect.classify_frame(txt(scene(2, True), "busted", (200, 80, 30))) == "busted")
check("MISSION PASSED", detect.classify_frame(txt(scene(3), "MISSION PASSED", (40, 190, 240), 0.95)) == "passed")
check("estrellas de policía", detect.classify_frame(stars) == "stars")
check("escena normal = nada", detect.classify_frame(scene(5)) is None)
check("coche rojo en escena a color no es WASTED", detect.classify_frame(red_car) is None)
check("imagen diminuta = nada, sin error", detect.classify_frame(np.zeros((10, 10, 3), np.uint8)) is None)
ev = detect.confirm_events([None, "wasted", None, "wasted", "wasted", "wasted", None, "stars", "stars", None])
check("un solo fotograma suelto no cuenta", 1 not in ev)
check("3 seguidos sí cuentan", ev.get(3) == "wasted" and ev.get(5) == "wasted")
check("estrellas necesitan 3 fotogramas", 7 not in ev)

# video real de 12 s: WASTED entre el segundo 5 y el 8 (ffmpeg lo lee de verdad)
import subprocess  # noqa: E402
vid = Path("/tmp/_p3_video.mp4")
pr = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", "10", "-i", "-",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vid)], stdin=subprocess.PIPE)
fw, fn = txt(scene(1, True), "wasted", (30, 30, 200)), scene(5)
for i in range(120):
    pr.stdin.write((fw if 50 <= i < 80 else fn).tobytes())
pr.stdin.close(); pr.wait()
evs = detect.screen_events(vid)
check("screen_events lee un video real y encuentra el WASTED", set(evs) >= {5, 6, 7} and not (set(evs) & {0, 1, 2, 10, 11}))
check("screen_events: archivo inexistente = vacío", detect.screen_events(Path("/tmp/nada.mp4")) == {})
fr = vision.frames(vid, 2.0, 10.0, 3)
check("vision.frames saca 3 JPEG reales", len(fr) == 3 and all(f[:2] == b"\xff\xd8" for f in fr))
check("vision.frames: archivo inexistente = lista vacía", vision.frames(Path("/tmp/nada.mp4"), 0, 5, 3) == [])

# ----------------------------------------------------------------- 3) discusiones (reality)
words = []
for sec in range(0, 60):                 # charla tranquila: 2 palabras/s
    words += [{"w": "x", "start": sec + 0.1, "end": sec + 0.3}, {"w": "y", "start": sec + 0.5, "end": sec + 0.7}]
fight = range(30, 42)                    # pelea: 5 palabras/s y a gritos
words = [w for w in words if int(w["start"]) not in fight]
for sec in fight:
    words += [{"w": "z", "start": sec + i * 0.2, "end": sec + i * 0.2 + 0.15} for i in range(5)]
lv = [50.0 + (np.random.default_rng(sec).random() - 0.5) for sec in range(60)]
for sec in fight:
    lv[sec] += 12
arg = detect.argument_from_signals(words, lv, set(), lo=0, hi=60)
check("pelea detectada", len(arg & set(fight)) >= 8)
check("charla tranquila no es pelea", not (arg & set(range(0, 20))))
check("un grito suelto sin habla rápida no es pelea",
      detect.argument_from_signals([w for w in words if int(w["start"]) not in fight], lv, set(), lo=0, hi=60) == set())
check("sin datos = vacío", detect.argument_from_signals([], [], set()) == set() and detect.argument_seconds(None, None) == set())
lv2 = lv[20:]                            # niveles que empiezan en el segundo 20 (modo en vivo)
check("en vivo (lo=20) da lo mismo",
      len(detect.argument_from_signals([w for w in words if w["start"] >= 20], lv2, set(), lo=20, hi=60) & set(fight)) >= 8)

# ----------------------------------------------------------------- 4) repetidos entre cámaras
cam_a = "No me grites en mi cara, tú eres una hipócrita y todo el mundo lo sabe, yo no voy a callarme más"
cam_b = "no me grites en mi cara tú eres una hipócrita y todo el mundo lo sabe yo no voy a callarme"
otro = "Mañana toca nominación y nadie quiere salir de la casa, Pedro dice que se va a salvar con el voto"
check("misma escena de otra cámara = muy parecida", detect.similarity(detect.fingerprint(cam_a), detect.fingerprint(cam_b)) > 0.7)
check("otra escena = poco parecida", detect.similarity(detect.fingerprint(cam_a), detect.fingerprint(otro)) < 0.2)
ms = [{"title": "A", "score": 90, "t": cam_a}, {"title": "B", "score": 80, "t": cam_b}, {"title": "C", "score": 70, "t": otro}]
kept, dropped = detect.drop_repeats(ms, lambda m: m["t"])
check("repetido dentro del mismo video se quita", [m["title"] for m in kept] == ["A", "C"] and dropped[0]["title"] == "B")
kept, dropped = detect.drop_repeats(ms, lambda m: m["t"], known=[cam_b])
check("repetido de un clip ya publicado se quita", [m["title"] for m in kept] == ["C"])
kept, _d = detect.drop_repeats([{"title": "corto", "score": 50, "t": "sí"}, {"title": "corto2", "score": 40, "t": "sí"}], lambda m: m["t"])
check("textos muy cortos no se comparan", len(kept) == 2)

# ----------------------------------------------------------------- 5) marcas y puntaje
segs = [{"start": 0.0, "end": 4.0, "text": "hola"}, {"start": 20.0, "end": 24.0, "text": "me mataron"}]
extra = {"💥": {21, 22}, "📺": {23}}
n = energy.annotate(segs, set(), set(), set(), extra=extra, labels={23: "WASTED"})
check("annotate marca 💥 y 📺 y deja nota", n == 1 and "💥" in segs[1]["hot"] and "📺" in segs[1]["hot"] and segs[1]["note"] == "pantalla: WASTED")
check("sin marcas no cambia nada", segs[0]["hot"] == "" and "note" not in segs[0])
out = energy.add_action_markers([{"start": 0.0, "end": 2.0, "text": "hola"}], set(), set(), set(), extra={"💥": {30, 31}}, labels={})
check("explosión sin voz crea [acción sin voz]", any(s["text"] == energy.ACTION_TEXT and "💥" in s["hot"] for s in out))
check("la IA ve la nota", "(pantalla: WASTED)" in analyze._line(segs[1]))
prof = profiles.get("gta")
c1 = [{"start": 18.0, "end": 40.0, "score": 60, "title": "t", "reason": ""}]
analyze._boost(c1, segs, prof)
check("💥 y 📺 suben el puntaje en GTA", c1[0]["score"] > 60)
check("cada detector de un perfil tiene su bonus", all(sg in profiles.get(tp)["bonus"] for tp in profiles.TYPES for sg in profiles.get(tp).get("signals", {})))
check("reality usa discusión; gta usa combate y pantalla",
      profiles.get("reality")["signals"] == {"argument": True} and profiles.get("gta")["signals"] == {"combat": True, "screen": True})
check("el prompt explica las marcas nuevas", all(m in analyze._build_prompt(segs, 3, 25, prof, "GTA 5") for m in "💥📺🗯"))

# ----------------------------------------------------------------- 6) verificación con imágenes (con respuestas simuladas)
config.VERIFY_IMAGES = "auto"
check("auto: GTA y reality verifican, podcast no", vision.enabled(profiles.get("gta")) and vision.enabled(profiles.get("reality"))
      and not vision.enabled(profiles.get("podcast")))
os.environ["GEMINI_API_KEY"] = "g_x"
check("hay visión con Gemini/Groq configurado", llm.vision_available())
m_ = {"score": 80, "reason": "", "title": "x"}
vision.adjust(m_, {"verdict": "bad", "score": 5, "problem": "menú de pausa"})
check("imagen mala baja el clip a 35 o menos", m_["score"] <= 35 and "menú" in m_["reason"])
m_ = {"score": 70, "reason": "", "title": "x"}
vision.adjust(m_, {"verdict": "strong", "score": 95})
check("imagen fuerte lo sube un poco", 70 < m_["score"] <= 100)
m_ = {"score": 70, "reason": "", "title": "x"}
vision.adjust(m_, {"verdict": "ok", "score": 70})
check("imagen normal no cambia", m_["score"] == 70)
check("_parse acepta JSON válido y rechaza basura", vision._parse('hola {"verdict":"ok","score":50}') and vision._parse("nada") is None
      and vision._parse('{"verdict":"raro"}') is None)

calls = []


def fake_ask_vision(prompt, imgs, check=None):
    calls.append(len(imgs))
    if "Boom" in prompt:
        raise llm.AllBusy("sin cupo")
    return check('{"verdict":"bad","score":10,"problem":"pantalla de carga"}')


real_ask, real_frames = llm.ask_vision, vision.frames
llm.ask_vision, vision.frames = fake_ask_vision, lambda v, s, e, n=3, width=512: [b"x" * 600] * n
config.VERIFY_IMAGES = "1"
cs = [{"start": 0, "end": 30, "score": 90, "title": "Uno", "reason": ""}, {"start": 40, "end": 70, "score": 80, "title": "Boom", "reason": ""},
      {"start": 80, "end": 110, "score": 70, "title": "Tres", "reason": ""}]
n_ = vision.verify(cs, Path("v.mp4"), profiles.get("gta"), lambda m, lim=None: "texto")
check("verify revisa y baja el clip malo", n_ == 1 and cs[0]["score"] <= 35 and calls == [3, 3])
check("si se acaba el cupo, para y deja el resto igual", cs[1]["score"] == 80 and cs[2]["score"] == 70)
config.VERIFY_IMAGES = "0"
check("VERIFY_IMAGES=0 la apaga", vision.verify(cs, Path("v.mp4"), profiles.get("gta"), lambda m, lim=None: "") == 0)
llm.ask_vision, vision.frames = real_ask, real_frames

# ----------------------------------------------------------------- 7) ask_vision manda imágenes y rota (requests simulado)
sent = []


class Resp:
    def __init__(self, status, body):
        self.status_code, self._b, self.text, self.headers = status, body, str(body), {}

    ok = property(lambda s: 200 <= s.status_code < 300)

    def json(self):
        return self._b


def fake_post(url, headers=None, json=None, timeout=None, **kw):
    sent.append((url.split("/")[2], json["model"], json["messages"][0]["content"], json.get("response_format")))
    if "groq" in url:
        return Resp(429, "rate limit per minute")
    return Resp(200, {"choices": [{"message": {"content": '{"verdict":"ok","score":60}'}}]})


sys.modules["requests"] = types.SimpleNamespace(post=fake_post, RequestException=OSError)
res = llm.ask_vision("mira", [b"\xff\xd8abc", b"\xff\xd8def"], check=vision._parse)
check("Groq sin cupo → pasa a Gemini con visión", res["verdict"] == "ok" and sent[0][0] == "api.groq.com" and "gemini" in sent[1][0] or "generativelanguage" in sent[1][0])
check("la petición lleva las imágenes en base64", isinstance(sent[0][2], list) and sent[0][2][1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
check("Groq usa su modelo de visión", "llama-4" in sent[0][1])
check("con imágenes no se fuerza modo JSON", sent[0][3] is None)
sent.clear()
llm.ask_vision("mira", [b"x"], check=vision._parse)
check("el cupo agotado de visión no bloquea el texto", llm._ready("groq") and not llm._ready("groq:vision") and sent[0][0] != "api.groq.com")

# ----------------------------------------------------------------- 8) find_moments completo (IA simulada)
sg = [{"start": 0.0, "end": 30.0, "text": cam_a}, {"start": 100.0, "end": 130.0, "text": cam_b}, {"start": 200.0, "end": 230.0, "text": otro}]
fake = lambda ch, want, secs, prof=None, game=None: [  # noqa: E731
    {"start": 0, "end": 30, "score": 80, "title": "Cam A"}, {"start": 100, "end": 130, "score": 78, "title": "Cam B"},
    {"start": 200, "end": 230, "score": 70, "title": "Otra"}]
analyze_ask, analyze.llm_rerank = analyze._ask_llm, None
analyze._ask_llm = fake
config.RERANK, config.VERIFY_IMAGES = False, "0"
ch, rej = analyze.find_moments(sg, 5, 30, profile="reality")
check("reality: la otra cámara se descarta", sorted(m["title"] for m in ch) == ["Cam A", "Otra"] and any("Repetido" in r["reason"] for r in rej))
ch, rej = analyze.find_moments(sg, 5, 30, profile="reality", known_texts=[cam_a])
check("reality: lo ya publicado no se repite", [m["title"] for m in ch] == ["Otra"])
ch, rej = analyze.find_moments(sg, 5, 30, profile="podcast")
check("podcast: no se filtra nada", len(ch) == 3)
config.DEDUPE = False
ch, rej = analyze.find_moments(sg, 5, 30, profile="reality")
check("DEDUPE=0 lo apaga", len(ch) == 3)
analyze._ask_llm = analyze_ask

print(f"OK: {ok} pruebas de la Parte 3 pasaron")
