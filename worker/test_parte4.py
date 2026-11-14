"""Pruebas de la Parte 4 (audio, efectos, cámara de streamer, GPU, subtítulos por persona). Sin internet. Ejecuta: python test_parte4.py"""
import os
import subprocess
import tempfile
from pathlib import Path

import dotenv

dotenv.load_dotenv = lambda *a, **k: False
for k in list(os.environ):
    if k.startswith(("CLIP_", "BLEEP_", "SUBS_", "HF_")):
        del os.environ[k]

import numpy as np  # noqa: E402

import config  # noqa: E402
import encoder  # noqa: E402
import framing  # noqa: E402
import postfx  # noqa: E402
import profiles  # noqa: E402
import render  # noqa: E402
import speakers  # noqa: E402

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


# ---------------- groserías
for w in ("puta", "¡Coño!", "MIERDA", "Mamagüevo", "fuck", "Cabrón,", "hijueputa", "puñeta"):
    check(f"grosería: {w}", postfx.is_profane(w))
for w in ("Singapur", "computadora", "vergüenza", "ridículo", "cono", "Putin", "pingüino", "disputa", "culpa", "hola", "chingón"):
    check(f"NO es grosería: {w}", not postfx.is_profane(w))
check("keep gana", not postfx.is_profane("puta", keep={"puta"}))
check("extra suma", postfx.is_profane("zorra", extra={"zorra"}, keep=set()))
W = [{"w": "hola", "start": 1.0, "end": 1.3}, {"w": "mierda,", "start": 2.0, "end": 2.1}, {"w": "puta", "start": 2.15, "end": 2.4},
     {"w": "coño", "start": 8.0, "end": 8.4}, {"w": "puto", "start": 30.0, "end": 30.3}]
b = postfx.find_profanity(W, 0.0, 10.0)
check("fusiona pegadas y descarta las de fuera", len(b) == 2 and b[0][0] < 2.0 and b[0][1] > 2.4 and b[1][0] < 8.0)
check("mínimo de duración", all(y - x >= postfx.MIN_BEEP - 1e-6 for x, y in b))
b2 = postfx.find_profanity(W, 5.0, 15.0)
check("tiempos relativos al clip", len(b2) == 1 and 2.8 < b2[0][0] < 3.0)
cw = postfx.censor_words(W)
check("censura subtítulo", cw[1]["w"].startswith("m") and "*" in cw[1]["w"] and cw[1]["w"].endswith(",") and cw[0]["w"] == "hola")

# ---------------- volumen
j = 'ruido\n{\n\t"input_i" : "-27.50",\n\t"input_tp" : "-9.1",\n\t"input_lra" : "3.2",\n\t"input_thresh" : "-38.0",\n\t"target_offset" : "0.4"\n}\n'
m = postfx.parse_loudnorm(j)
check("parse loudnorm", m and abs(m["input_i"] + 27.5) < 1e-9)
check("silencio -> None", postfx.parse_loudnorm(j.replace("-27.50", "-inf")) is None)
check("filtro 2 pasadas", "linear=true" in postfx.loudnorm_filter(m) and "linear" not in postfx.loudnorm_filter(None))

# ---------------- decidir efectos
check("explosión -> cámara lenta + zoom", (lambda f: f and f["slow"] and abs(f["slow"][0] - 9.75) < 1e-6 and f["zoom"])(postfx.choose_fx([(10.0, "boom")], 30)))
check("no en el gancho", postfx.choose_fx([(1.0, "boom")], 30) is None)
check("no en el remate", postfx.choose_fx([(28.0, "boom")], 30) is None)
check("clip muy corto: nada", postfx.choose_fx([(5.0, "boom")], 6) is None)
f = postfx.choose_fx([(10.0, "shot"), (10.3, "shot"), (10.7, "shot")], 30)
check("ráfaga -> solo zoom", f and f["slow"] is None and len(f["zoom"]) == 1)
check("disparo suelto: nada", postfx.choose_fx([(10.0, "shot")], 30) is None)
check("pico de volumen -> zoom suave", (lambda f: f and f["zoom"][0][2] < 0.1)(postfx.choose_fx([], 30, peak=(12.0, 9.0))))
check("pico flojo: nada", postfx.choose_fx([], 30, peak=(12.0, 3.0)) is None)
f = postfx.choose_fx([(10.0, "boom")], 30, want_slow=False)
check("sin slow queda zoom", f and f["slow"] is None and f["zoom"])
check("rate se limita a 0.5", postfx.choose_fx([(10.0, "boom")], 30, rate=0.2)["slow"][2] == 0.5)
tm = postfx.make_tmap((10.0, 11.0, 0.5))
check("mapa de tiempos", tm(5) == 5 and abs(tm(10.5) - 11.0) < 1e-9 and abs(tm(12) - 13.0) < 1e-9)
check("duración final", abs(postfx.out_duration(30, (10.0, 11.0, 0.5)) - 31.0) < 1e-9 and postfx.out_duration(30, None) == 30)
check("perfiles", postfx.wants(profiles.get("gta")) == (True, True) and postfx.wants(profiles.get("reality")) == (True, False)
      and postfx.wants(profiles.get("podcast")) == (False, False))
config.CLIP_ZOOM = "1"
check(".env fuerza zoom", postfx.wants(profiles.get("podcast"))[0] is True)
check("opción del trabajo gana al .env", postfx.wants(profiles.get("podcast"), {"zoom": False})[0] is False)
config.CLIP_ZOOM = "auto"

# ---------------- subtítulos: tiempos con cámara lenta y color por persona
ws = [{"w": "uno", "start": 1.0, "end": 1.5, "spk": 0}, {"w": "dos", "start": 12.0, "end": 12.5, "spk": 1}]
ass = render.build_ass(ws, 0, 20, tmap=postfx.make_tmap((10.0, 11.0, 0.5)), n_speakers=2)
check("subtítulo se corre tras la cámara lenta", "0:00:13.00" in ass and "0:00:01.00" in ass)
check("dos colores", "&H" + render._hex(speakers.PALETTE[0]) + "&" in ass)
check("sin personas: un solo color", "&H" + render._hex(speakers.PALETTE[0]) + "&" not in render.build_ass(ws, 0, 20))

# ---------------- personas
turns = [(0, 5, "A"), (5, 10, "B")]
lab, n = speakers.assign([{"w": "x", "start": 1, "end": 2}, {"w": "y", "start": 6, "end": 7}, {"w": "z", "start": 20, "end": 21}], turns)
check("asigna personas", n == 2 and lab[0]["spk"] == 0 and lab[1]["spk"] == 1 and "spk" not in lab[2])
sm = speakers.smooth([{"w": "a", "start": 0, "end": .3, "spk": 0}, {"w": "b", "start": .4, "end": .6, "spk": 1}, {"w": "c", "start": .7, "end": 1, "spk": 0}])
check("alisa parpadeo", sm[1]["spk"] == 0)
check("colores sin repetir", len(set(speakers.colors(3, "#FFE000"))) == 3 and speakers.colors(2, "FFE000")[0] == "FFE000")
check("sin HF_TOKEN no hay personas", not speakers.available())

# ---------------- GPU
check("cpu por defecto de prueba", encoder.pick("cpu") == "cpu")
for kind, codec in (("nvenc", "h264_nvenc"), ("qsv", "h264_qsv"), ("amf", "h264_amf"), ("videotoolbox", "h264_videotoolbox"), ("cpu", "libx264")):
    check(f"args {kind}", codec in encoder.video_args(kind, 17, "medium", 10_000_000))
encoder._cache.clear(); encoder._bad.clear()
encoder._works = lambda k: k == "qsv"
check("auto elige la GPU que funciona", encoder.pick("auto") == "qsv")
encoder.mark_bad("qsv")
check("GPU mala -> CPU", encoder.pick("auto") == "cpu")
encoder._cache.clear(); encoder._bad.clear()
encoder._works = lambda k: False
check("sin GPU -> CPU", encoder.pick("auto") == "cpu" and encoder.pick("nvenc") == "cpu")

# ---------------- cámara de streamer (lógica pura)
face = framing.facecam_pick([[{"x": 0.85, "y": 0.8, "w": 0.06}] for _ in range(10)], 10)
check("cámara en esquina", face and face["x"] > 0.8)
check("cara grande en el centro: no es cámara", framing.facecam_pick([[{"x": 0.5, "y": 0.5, "w": 0.3}] for _ in range(10)], 10) is None)
check("cara que salta: no es cámara", framing.facecam_pick([[{"x": 0.1 + 0.08 * i, "y": 0.8, "w": 0.06}] for i in range(10)], 10) is None)
box = framing.panel_in_rect((0.78, 0.7, 1.0, 1.0), {"x": 0.89, "y": 0.84, "w": 0.06}, 1920, 1080, 1080 / 1312)
check("panel dentro del recuadro", box["x"] >= 78 - 0.05 and box["x"] + box["w"] <= 100.05 and box["y"] >= 70 - 0.05 and box["y"] + box["h"] <= 100.05)

# ---------------- ffmpeg real
tmp = Path(tempfile.mkdtemp())
rng = np.random.default_rng(3)


def wav(path, sig, sr=16000):
    import wave
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((np.clip(sig, -1, 1) * 32767).astype(np.int16).tobytes())


def mux(vid, aud, out, secs):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=30:d={secs}", "-i", str(aud),
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)], check=True)


def pcm(path, t0, t1):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t0), "-t", str(t1 - t0), "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def peak_hz(x):
    s = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.fft.rfftfreq(len(x), 1 / 16000)[int(np.argmax(s))]


def dims_dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height:format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True).stdout.split()
    return r


# a) pitido: tono de 440 Hz, groserías en 2.0-2.4 s
t = np.arange(16000 * 10) / 16000
wav(tmp / "a.wav", 0.3 * np.sin(2 * np.pi * 440 * t))
mux(None, tmp / "a.wav", tmp / "a.mp4", 10)
config.CLIP_LOUDNORM = False
config.CLIP_ZOOM = config.CLIP_SLOWMO = "0"
o = tmp / "o_beep.mp4"
render.render_clip(tmp / "a.mp4", [{"w": "mierda", "start": 2.0, "end": 2.4}, {"w": "hola", "start": 4.0, "end": 4.4}], 0.0, 9.0, o, tmp)
check("pitido a 1 kHz sobre la grosería", abs(peak_hz(pcm(o, 2.1, 2.3)) - 1000) < 60)
check("fuera de la grosería sigue el audio", abs(peak_hz(pcm(o, 5.0, 6.0)) - 440) < 20)
check("clip 1080x1920", dims_dur(o)[:1] == ["1080,1920"] or "1080" in dims_dur(o)[0])
o2 = tmp / "o_nobeep.mp4"
render.render_clip(tmp / "a.mp4", [{"w": "mierda", "start": 2.0, "end": 2.4}], 0.0, 9.0, o2, tmp, opts={"bleep": False})
check("bleep apagable desde las opciones", abs(peak_hz(pcm(o2, 2.1, 2.3)) - 440) < 20)

# b) volumen: ruido muy bajo -> -14 LUFS
wav(tmp / "q.wav", rng.normal(0, 0.02, 16000 * 12))
mux(None, tmp / "q.wav", tmp / "q.mp4", 12)
config.CLIP_LOUDNORM = True
o = tmp / "o_loud.mp4"
render.render_clip(tmp / "q.mp4", [], 0.0, 11.0, o, tmp)
got = postfx.measure_loudness(o, 0, 10.5)
check("volumen final ≈ -14 LUFS", got and abs(got["input_i"] + 14) < 1.0)
config.CLIP_LOUDNORM = False

# c) explosión: cámara lenta + zoom, el video queda más largo y los subtítulos siguen
sig = rng.normal(0, 1, 16000 * 14).astype(np.float32)
sig = np.convolve(sig, np.ones(8) / 8, "same") * 0.03
n = int(1.2 * 16000); i = 6 * 16000
bm = np.convolve(rng.normal(0, 1, n), np.ones(40) / 40, "same") * 6 * np.exp(-np.arange(n) / (0.35 * 16000)) * 0.8
sig[i:i + n] += bm
wav(tmp / "b.wav", sig)
mux(None, tmp / "b.wav", tmp / "b.mp4", 14)
check("el análisis ve la explosión", any(k == "boom" and 5.8 < tt < 6.4 for tt, k in postfx.analyze_clip_audio(tmp / "b.mp4", 0, 14)[0]))
config.CLIP_ZOOM = config.CLIP_SLOWMO = "auto"
o = tmp / "o_fx.mp4"
render.render_clip(tmp / "b.mp4", [{"w": "boom", "start": 8.0, "end": 8.4}], 0.0, 13.0, o, tmp, profile=profiles.get("gta"))
d = float(dims_dur(o)[-1])
check("cámara lenta alarga el clip ~1.2 s", 13.8 < d < 14.6)
o3 = tmp / "o_nofx.mp4"
render.render_clip(tmp / "b.mp4", [], 0.0, 13.0, o3, tmp, profile=profiles.get("podcast"))
check("podcast sin efectos", 12.7 < float(dims_dur(o3)[-1]) < 13.3)

# d) la GPU falla -> el clip sale igual con CPU
encoder._cache.clear(); encoder._bad.clear()
encoder._works = lambda k: k == "nvenc"
o = tmp / "o_gpu.mp4"
render.render_clip(tmp / "a.mp4", [], 0.0, 5.0, o, tmp)
check("fallback a CPU cuando la GPU falla", o.exists() and o.stat().st_size > 10_000 and "nvenc" in encoder._bad)

# e) cámara de streamer: juego en movimiento + recuadro fijo con una cara en la esquina
from PIL import Image  # noqa: E402
from skimage import data  # noqa: E402

astro = Image.fromarray(data.astronaut()).resize((300, 300))
p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "1920x1080", "-r", "6", "-i", "-",
                      "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p", str(tmp / "fc.mp4")], stdin=subprocess.PIPE)
base = (rng.random((1080 // 8, 1920 // 8, 3)) * 255).astype(np.uint8)
for k in range(6 * 5):
    game = np.roll(base, (k * 3, k * 5), (0, 1)).repeat(8, 0).repeat(8, 1)
    cv = Image.fromarray(game)
    cv.paste(Image.new("RGB", (420, 320), (20, 20, 20)), (1460, 720))
    cv.paste(astro, (1520, 730))
    p.stdin.write(cv.tobytes())
p.stdin.close(); p.wait()
fb = framing.facecam_box(tmp / "fc.mp4", 0, 5, 1920, 1080, 1080 / 1312)
check("encuentra la cámara en la esquina", fb and fb["x"] > 70 and fb["y"] > 60)
check("el panel queda dentro de la cámara (sin juego)", fb and fb["x"] >= 1460 / 19.2 - 1.5 and fb["x"] + fb["w"] <= 1880 / 19.2 + 1.5
      and fb["y"] >= 720 / 10.8 - 1.5 and fb["y"] + fb["h"] <= 1040 / 10.8 + 1.5)
check("sin cámara superpuesta: None", framing.facecam_box(tmp / "a.mp4", 0, 5, 1280, 720, 0.82) is None)

print(f"OK: Parte 4, {ok} pruebas")
