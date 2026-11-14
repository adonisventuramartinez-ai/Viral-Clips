"""Parte 4: elige el codificador de video (GPU si hay, CPU si no) y arma sus argumentos para ffmpeg.

Los filtros (recorte, subtítulos, zoom) siguen corriendo en el CPU; la GPU solo codifica el resultado.
Por eso el ahorro es de "algo más rápido", no de "diez veces". Si la GPU falla a mitad de un clip, render.py repite con CPU.
"""
import subprocess

import config

GPU = ("nvenc", "qsv", "amf", "videotoolbox")
_NAME = {"nvenc": "h264_nvenc", "qsv": "h264_qsv", "amf": "h264_amf", "videotoolbox": "h264_videotoolbox", "cpu": "libx264"}
_cache = {}
_bad = set()


def _works(kind):
    """Una codificación de prueba de 0.2 s: que ffmpeg liste el codificador no significa que haya tarjeta compatible."""
    cmd = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=30:d=0.3", "-an", "-c:v", _NAME[kind],
           "-pix_fmt", "yuv420p", "-f", "null", "-"]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def pick(requested=None):
    """'cpu' | 'nvenc' | 'qsv' | 'amf' | 'videotoolbox'. Con 'auto' prueba cada GPU una vez y recuerda el resultado."""
    req = (requested or config.CLIP_ENCODER or "auto").strip().lower()
    if req in ("cpu", "libx264", "x264", "0", "off"):
        return "cpu"
    if req in GPU:
        if req in _bad:
            return "cpu"
        if req not in _cache:
            _cache[req] = _works(req)
            if not _cache[req]:
                print(f"  Codificador: {req} no funciona en este equipo, uso CPU.", flush=True)
        return req if _cache[req] else "cpu"
    for kind in GPU:                                   # auto
        if kind in _bad:
            continue
        if kind not in _cache:
            _cache[kind] = _works(kind)
        if _cache[kind]:
            return kind
    return "cpu"


def mark_bad(kind):
    """La GPU falló codificando un clip real: no se vuelve a intentar en esta sesión."""
    _bad.add(kind)
    _cache[kind] = False


def video_args(kind, crf, preset, vb):
    """Argumentos de codificación de video para ffmpeg. vb = bitrate máximo (bits/s)."""
    cap = ["-maxrate", str(vb), "-bufsize", str(vb * 2)]
    if kind == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", str(crf + 2), "-b:v", "0",
                "-spatial-aq", "1", "-profile:v", "high", "-level", "4.2"] + cap + ["-pix_fmt", "yuv420p"]
    if kind == "qsv":
        return ["-c:v", "h264_qsv", "-global_quality", str(crf + 2), "-preset", "slower", "-profile:v", "high"] + cap + ["-pix_fmt", "nv12"]
    if kind == "amf":
        return ["-c:v", "h264_amf", "-quality", "quality", "-rc", "vbr_peak", "-b:v", str(int(vb * 0.8)), "-profile:v", "high"] + \
               ["-maxrate", str(vb), "-bufsize", str(vb * 2), "-pix_fmt", "yuv420p"]
    if kind == "videotoolbox":
        return ["-c:v", "h264_videotoolbox", "-b:v", str(int(vb * 0.8)), "-profile:v", "high", "-allow_sw", "1", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high", "-level", "4.2"] + cap + ["-pix_fmt", "yuv420p"]
