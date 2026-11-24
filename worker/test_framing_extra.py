"""Mejora 1: pruebas extra del encuadre (sin OpenCV ni ffmpeg). Ejecuta: python test_framing_extra.py"""
import framing

CROP = 0.3158
FPS = framing.SAMPLE_FPS


def samples(spec, n):
    return [{"t": i / FPS, "faces": [{"x": x, "w": w, "m": m} for x, w, m in spec(i)]} for i in range(n)]


# 1) la persona camina hacia el borde del recuadro: la cámara la alcanza en menos de 1.2 s (antes tardaba ~2 s)
def walk(i):
    return [(0.30, 0.08, 1)] if i < 30 else [(0.30 + 0.17, 0.08, 1)]   # salta a 0.47 (fuera del recuadro centrado en 0.30)
k = framing.plan(samples(walk, 60), CROP)
assert len(k) == 3, k
assert k[1][0] - 10.0 < 1.0, k   # empieza a moverse casi de inmediato

# 2) dos cuadros sueltos distintos NO mueven la cámara
def blip2(i):
    return [(0.8, 0.08, 1)] if i in (20, 22) else [(0.25, 0.08, 1)]
k = framing.plan(samples(blip2, 60), CROP)
assert len(k) == 1, k

# 3) cambio de hablante rápido: la cámara llega antes de 3 s tras el cambio
def swap(i):
    l = i < 30
    return [(0.2, 0.08, 6 if l else 0.3), (0.8, 0.08, 0.3 if l else 6)]
k = framing.plan(samples(swap, 60), CROP)
assert k[-1][0] < 10.0 + 3.0, k

# 4) _load nunca revienta aunque falten los .xml de OpenCV
assert framing._load()[0] in ("cv2", "sk")
print("OK: mejora 1, encuadre (4 pruebas)")
