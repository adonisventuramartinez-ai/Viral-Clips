"""Parte 15: Modo Original brutal (apertura directa, dramómetro animado, encuesta con paneles, tope de tamaño). Ejecuta: python test_original2.py"""
import subprocess
import tempfile
from pathlib import Path

import config
import original

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


tmp = Path(tempfile.mkdtemp())

# ---- ajustes
check("por defecto arranca directo (cold)", config.INTRO_MODE == "cold" and original.DEFAULTS["intro"] == "cold")
check("inicio inteligente encendido por defecto", config.SMART_START is True and original.DEFAULTS["smart_start"] is True)
check("load() devuelve intro válido", original.load(tmp)["intro"] in ("cold", "card"))

# ---- dramómetro animado
original._meter_ass(88, tmp / "m.ass", intro="Antes de esto, algo pasó", show_meter=True)
a = (tmp / "m.ass").read_text(encoding="utf-8")
check("el dramómetro muestra el nivel", "DRAMÓMETRO 88% · NIVEL MÁXIMO EXPLOSIVO" in a)
check("la barra se llena con animación (\\clip)", "\\t(0,1100,\\clip(" in a)
check("la barra termina en el % correcto", f"\\clip({220},{190},{220 + 640 * 88 // 100},{250})" in a)
check("el contexto sale después del gancho (0.9 s)", "0:00:00.90" in a and ",Intro," in a)
check("niveles del dramómetro", original._meter_level(40) == "CALENTITO" and original._meter_level(60) == "TENSO" and original._meter_level(90) == "EXPLOSIVO")
original._meter_ass(50, tmp / "m2.ass", intro=None, show_meter=False)
b = (tmp / "m2.ass").read_text(encoding="utf-8")
check("sin dramómetro ni intro no hay eventos", "Dialogue" not in b)
original._meter_ass(10, tmp / "m3.ass", intro=None, show_meter=True)
check("el % se limita a 35-99", "35%" in (tmp / "m3.ass").read_text(encoding="utf-8"))

# ---- encuesta con paneles
p = {"q": "¿Quién tiene la razón?", "a": "Team Alofoke", "b": "Team Invitado"}
ass = original._poll_ass(p, "@MiPagina", 3.0)
check("pregunta, A, B y CTA presentes", all(x in ass for x in ("¿Quién tiene la razón?", "Team Alofoke", "Team Invitado", "COMENTA A O B")))
check("dos paneles de color distintos", original.POLL_A in ass and original.POLL_B in ass and original.POLL_A != original.POLL_B)
check("los paneles entran deslizando", ass.count("\\move(-1080,0,0,0,") == 2)
check("sale el nombre de la página", "@MiPagina" in ass)
check("sin página no hay línea de página", ",Page," not in original._poll_ass(p, "", 3.0).split("[Events]")[1])
check("la opción larga baja de tamaño", "\\fs46" in original._poll_ass({"q": "q", "a": "x" * 22, "b": "y"}, "", 3.0))
check("las llaves del texto no rompen el ASS", "{" not in original._esc("hola {mundo}") and "(" in original._esc("hola {mundo}"))

# ---- tope de tamaño
for d in (20, 45, 60, 90, 120, 180, 300):
    cap = original.size_cap(d)
    check(f"{d}s: el archivo no pasa de CLIP_MAX_MB", cap == 1_000_000 or (cap + 192_000) * d / 8 <= config.CLIP_MAX_MB * 1e6 * 1.001)
    check(f"{d}s: y siempre queda bajo los 50 MB de Supabase", (cap + 192_000) * d / 8 < 50e6)
check("CLIP_MAX_MB nunca llega a 50", config.CLIP_MAX_MB <= 49)

# ---- corrida real con ffmpeg: la apertura directa NO tiene nada antes del video
clip = tmp / "clip.mp4"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=2",
                "-f", "lavfi", "-i", "sine=frequency=300:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(clip)],
               check=True)
cfg = original.load(tmp)
cfg.update(narrate=False, page="@Pag", show="Programa", meter=True, poll=True)
ex = {"context": "Antes de esto, ya venían discutiendo", "outro": "¿Y tú qué opinas?", "poll": p, "caption": "x"}
res = {}
for mode in ("cold", "card"):
    cfg["intro"] = mode
    o = tmp / f"o_{mode}.mp4"
    original.wrap_clip(clip, ex, o, tmp, cfg, score=80)
    res[mode] = original._dur(o)
check("apertura directa dura clip + cierre (sin tarjeta antes)", abs(res["cold"] - (2.0 + 2.8)) < 0.6)
check("la tarjeta de antes añade ~2 s de espera", res["card"] - res["cold"] > 1.8)
# el primer cuadro del modo directo es el del clip (testsrc2 es muy colorido; una tarjeta es oscura)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp / "o_cold.mp4"), "-frames:v", "1", str(tmp / "f.png")], check=True)
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
px = np.asarray(Image.open(tmp / "f.png").convert("RGB").resize((32, 56)))
bright = float((px.max(axis=2) > 180).mean())
check("el primer cuadro ya es el video (no una tarjeta oscura)", bright > 0.25)

# ---- sin encuesta usa el cierre normal
cfg.update(poll=False, intro="cold")
original.wrap_clip(clip, {**ex, "poll": None}, tmp / "o_nopoll.mp4", tmp, cfg, score=60)
check("sin encuesta también termina bien", (tmp / "o_nopoll.mp4").exists() and original._dur(tmp / "o_nopoll.mp4") > 4)

# ---- TOP con fondos reales
comp = tmp / "top.mp4"
original.compilation([("Segundo", clip), ("Primero", clip)], "TOP 2 MOMENTOS", comp, tmp, cfg)
check("el TOP se genera con título + tarjetas + clips", comp.exists() and original._dur(comp) > 2.5 + 2 * (1.6 + 2.0) - 0.8)
check("el TOP no deja archivos temporales", not list(tmp.glob("comp_bg_*.png")))

print(f"OK: {ok} comprobaciones del Modo Original (Parte 15)")
