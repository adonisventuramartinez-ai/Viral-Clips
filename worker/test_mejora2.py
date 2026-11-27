"""Mejora 2: ritmo (silencios y muletillas) y zooms de corte. Ejecuta: python test_mejora2.py"""
import subprocess
import tempfile
from pathlib import Path

import config
import postfx
import profiles
import render
import tighten


def W(t, a, b):
    return {"w": t, "start": a, "end": b}


# 1) pausa larga en el medio: se acorta a ~0.3 s y las palabras se corren
words = [W("hola", 0.0, 0.4), W("a", 0.45, 0.6), W("todos", 0.65, 1.0), W("hoy", 1.05, 1.3), W("vamos", 1.35, 1.7),
         W("a", 1.75, 1.9), W("hablar", 4.4, 4.8), W("de", 4.85, 5.0), W("algo", 5.05, 5.4), W("serio", 5.45, 5.9),
         W("porque", 5.95, 6.3), W("importa", 6.35, 6.9), W("mucho", 6.95, 7.4), W("gracias", 7.45, 8.0)]
keeps, dropped = tighten.plan_cuts(words, 0.0, 10.0)
assert keeps and not dropped, keeps
total = sum(b - a for a, b in keeps)
assert 10.0 - total > 2.0, keeps          # quitó al menos 2 s (la pausa de ~2.5 s y el silencio final)
nw = tighten.new_words(words, keeps, dropped, 0.0, 10.0)
assert len(nw) == len(words)
gap = nw[6]["start"] - nw[5]["end"]
assert 0.2 < gap < 0.45, gap              # la pausa quedó en ~0.3 s
assert all(b["start"] >= a["start"] for a, b in zip(nw, nw[1:]))

# 2) muletillas: "eh" y "mmm" se van; "este" y "o sea" se quedan
words2 = [W("mira", 0.0, 0.3), W("eh", 0.4, 0.6), W("esto", 0.7, 1.0), W("mmm", 1.1, 1.5), W("es", 1.6, 1.7),
          W("este", 1.8, 2.0), W("problema", 2.1, 2.6), W("grande", 2.7, 3.1), W("o", 3.2, 3.3), W("sea", 3.35, 3.6),
          W("de", 3.7, 3.8), W("verdad", 3.9, 4.4), W("amigos", 4.5, 5.0), W("gracias", 5.1, 5.6)]
keeps2, dropped2 = tighten.plan_cuts(words2, 0.0, 9.0)
assert {words2[i]["w"] for i in dropped2} == {"eh", "mmm"}, dropped2
nw2 = tighten.new_words(words2, keeps2, dropped2, 0.0, 9.0)
assert [w["w"] for w in nw2 if w["w"] in ("este", "o", "sea")] == ["este", "o", "sea"]
assert "eh" not in [w["w"] for w in nw2]

# 3) nunca quita más del 30 % del clip
words3 = [W("uno", 0.0, 0.3), W("dos", 0.4, 0.7), W("tres", 5.0, 5.3), W("cuatro", 5.4, 5.7), W("cinco", 10.0, 10.3),
          W("seis", 10.4, 10.7), W("siete", 15.0, 15.3), W("ocho", 15.4, 15.7)]
keeps3, _ = tighten.plan_cuts(words3, 0.0, 20.0)
assert keeps3 is None or (20.0 - sum(b - a for a, b in keeps3)) <= 6.0 + 1e-6, keeps3

# 4) habla seguida sin pausas: no toca nada
words4 = [W(f"p{i}", i * 0.4, i * 0.4 + 0.3) for i in range(30)]
assert tighten.plan_cuts(words4, 0.0, 12.0)[0] is None

# 5) punch-in alterno: el primer tramo no tiene zoom, el segundo sí; nada antes de 2 s
z = tighten.punch_zooms([(0, 3.0), (5, 8.0), (9, 12.0), (14, 17.0)])
assert z and z[0][0] == 3.0 and abs(z[0][1] - 6.0) < 1e-6 and len(z) == 2, z
assert tighten.punch_zooms([(0, 1.0), (2, 3.5)]) == []     # cae antes de 2 s: sin zoom
assert len(tighten.punch_zooms([(i * 3, i * 3 + 2.0) for i in range(60)])) <= tighten.MAX_PUNCH

# 6) opciones: web > .env > perfil
assert postfx.wants_tighten(profiles.get("podcast"), {}) is True
assert postfx.wants_tighten(profiles.get("gta"), {}) is False
assert postfx.wants_tighten(profiles.get("gta"), {"tighten": "1"}) is True
assert postfx.wants_tighten(profiles.get("podcast"), {"tighten": "0"}) is False
print("OK: mejora 2, lógica de ritmo (6 grupos)")

# 7) ffmpeg real: video con silencio en medio -> sale más corto, con audio, y el render completo funciona
tmp = Path(tempfile.mkdtemp())
src = tmp / "src.mp4"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=440", "-t", "12", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
res = tighten.apply(src, words, 0.0, 10.0, tmp, "t")
assert res, "no recortó"
cut, nwords, dur, zooms = res
def probe(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)
assert abs(probe(cut) - dur) < 0.25, (probe(cut), dur)
assert render._probe(cut) == (1920, 1080)
assert postfx.has_audio(cut)
cut.unlink()
out = tmp / "o.mp4"
config.CLIP_FRAMING = "center"
render.render_clip(src, words, 0.0, 10.0, out, tmp, profile=profiles.get("podcast"), opts={"tighten": "1", "loudnorm": "0", "bleep": "0"})
assert out.exists() and abs(probe(out) - dur) < 0.4, (probe(out), dur)
assert render._probe(out) == (1080, 1920)
assert not list(tmp.glob("*_tight.mp4")), "dejó el archivo temporal"
out2 = tmp / "o2.mp4"      # sin ritmo: dura lo mismo que el original
render.render_clip(src, words, 0.0, 10.0, out2, tmp, profile=profiles.get("gta"), opts={"loudnorm": "0", "bleep": "0"})
assert abs(probe(out2) - 10.0) < 0.3
print("OK: mejora 2, recorte y render con ffmpeg real")
