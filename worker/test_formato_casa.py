"""Formato 'La Casa': cara grande arriba + fondo difuminado abajo.
Ejecuta: python test_formato_casa.py"""
from pathlib import Path

import config
import profiles
import render

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


config.CLIP_FRAMING = "center"   # el grafo se prueba sin llamar a ffmpeg

check("reality usa el formato Casa por defecto", profiles.layout_for(profiles.get("reality"), "crop") == "casa")
check("los juegos conservan el vertical", profiles.layout_for(profiles.get("gta6"), "crop") == "crop")
check("elegir Casa a mano se respeta", profiles.layout_for(profiles.get("podcast"), "casa") == "casa")
check("el recuadro manual manda", profiles.layout_for(profiles.get("reality"), "crop", {"x": 0, "y": 0, "w": 50, "h": 50}) == "crop")
config.CLIP_REALITY_LAYOUT = "crop"
check("se puede desactivar con CLIP_REALITY_LAYOUT", profiles.layout_for(profiles.get("reality"), "crop") == "crop")
config.CLIP_REALITY_LAYOUT = "casa"

render._probe = lambda source: (1920, 1080)
render._cam_box = lambda *a, **k: {"x": 30.0, "y": 0.0, "w": 40.0, "h": 95.0}
graph = render.layout_graph("casa", Path("video.mp4"), 0.0, 30.0, polish=False)
check("cara grande arriba", "scale=1080:1250" in graph and "vstack" in graph)
check("contexto difuminado abajo", "boxblur=12:3" in graph and "brightness=-0.18" in graph)
check("los subtítulos dejan espacio al panel de abajo", render.SUB_MARGIN["casa"] == 700)

print(f"FORMATO CASA OK ({ok} pruebas)")
