"""Formato 'La Casa' investigado: cara grande arriba, dúo cuando hay dos personas.
Ejecuta: python test_formato_casa.py"""
from pathlib import Path
import sys
import types

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
config.CLIP_REALITY_LAYOUT = "auto"

render._probe = lambda source: (1920, 1080)
render._cam_box = lambda *a, **k: {"x": 30.0, "y": 0.0, "w": 40.0, "h": 95.0}
graph = render.layout_graph("casa", Path("video.mp4"), 0.0, 30.0, polish=False)
check("cara grande arriba", "scale=1080:1500" in graph and "vstack" in graph)
check("contexto difuminado abajo", "scale=1080:420" in graph and "boxblur=12:3" in graph)
check("los subtítulos caen en la costura", render.SUB_MARGIN["casa"] == 450)

# Con dos caras claras, el perfil reality pasa a dúo (lo que recomiendan Opus/Cut.Pro).
config.CLIP_FRAMING = "auto"
framing = types.ModuleType("framing")
framing.duo_boxes = lambda *a, **k: ({"x": 0, "y": 0, "w": 50, "h": 50}, {"x": 50, "y": 0, "w": 50, "h": 50})
sys.modules["framing"] = framing
check("dos caras -> dúo en La Casa", render.reality_layout("casa", Path("v.mp4"), 0.0, 30.0,
                                                         profiles.get("reality"), 1920, 1080) == "duo")
check("un podcast no se vuelve dúo", render.reality_layout("casa", Path("v.mp4"), 0.0, 30.0,
                                                          profiles.get("podcast"), 1920, 1080) == "casa")
framing.duo_boxes = lambda *a, **k: None
check("sin dos caras se queda la Casa", render.reality_layout("casa", Path("v.mp4"), 0.0, 30.0,
                                                             profiles.get("reality"), 1920, 1080) == "casa")

print(f"FORMATO CASA OK ({ok} pruebas)")
