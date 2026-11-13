"""Modo Original (sin mostrar la cara ni hablar tú): convierte un corte en un clip con aporte propio.

Cada clip sale con:
  1. Tarjeta de CONTEXTO con VOZ NARRADORA (IA): explica qué pasó antes de que veas el momento.
  2. El clip, con un DRAMÓMETRO (barra de drama) los primeros segundos.
  3. Tarjeta de CIERRE con ENCUESTA A/B (la gente comenta A o B) y voz.
  + descripción con tu punto de vista y el crédito/permiso.
Además arma solo un TOP de los mejores momentos (cuenta regresiva #5 … #1) con voz.

Todo se configura desde la web (Ajustes → Modo Original). Si la voz o la IA fallan, el clip sale igual.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import config

W, H, FPS = 1080, 1920, 30

DEFAULTS = {
    "enabled": config.ORIGINAL_MODE, "show": config.SHOW_NAME, "page": config.PAGE_NAME, "credit": config.CREDIT_LINE,
    "narrate": True, "voice": config.NARRATOR_VOICE, "meter": True, "poll": True, "top": True, "top_n": 5,
}

PROMPT = """Eres el editor de una página de clips de "{show}" para Facebook. Español dominicano natural, sin groserías, sin insultos.
Del fragmento saca texto ORIGINAL (no copies frases largas textuales). Devuelve:
- context: 1 frase (máx 90 caracteres) para quien no vio el programa, que se pueda leer en voz alta ("Antes de esto, ...").
- outro: 1 pregunta corta (máx 60 caracteres) para comentar.
- poll: {{"q":"pregunta de 'quién tiene la razón' (máx 50 car.)","a":"opción A (máx 22 car.)","b":"opción B (máx 22 car.)"}}
- caption: descripción del post, 2 frases con punto de vista, sin spoilear el final.
Responde SOLO JSON: {{"context":"...","outro":"...","poll":{{"q":"...","a":"...","b":"..."}},"caption":"..."}}

Fragmento:
{text}"""


# ---------------------------------------------------------------- ajustes (los guarda la web)

def load(workdir=None):
    """Ajustes de Modo Original: valores por defecto + lo guardado en la web (Storage 'uploads', brand/original.json)."""
    cfg = dict(DEFAULTS)
    try:
        import db
        raw = db.sb.storage.from_("uploads").download("brand/original.json")
        saved = json.loads(raw.decode("utf-8")) if raw else {}
        cfg.update({k: saved[k] for k in DEFAULTS if k in saved})
    except Exception:  # noqa: BLE001  (nada guardado: se usan los valores del .env)
        pass
    cfg["top_n"] = int(min(10, max(3, int(cfg.get("top_n") or 5))))
    return cfg


# ---------------------------------------------------------------- IA y voz

def _parse(txt):
    m = re.search(r"\{.*\}", txt or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except ValueError:
        return None
    return d if isinstance(d, dict) and d.get("context") else None


def extras(text, cfg):
    """Texto original del clip. Si la IA falla usa frases genéricas (el clip no se cae)."""
    base = {"context": f"Momento clave de {cfg['show']}", "outro": "¿Tú qué piensas? Comenta.",
            "poll": None, "caption": ""}
    try:
        import llm
        d = llm.ask(PROMPT.format(show=cfg["show"], text=text[:2500]), check=_parse)
        for k in ("context", "outro", "caption"):
            if str(d.get(k, "")).strip():
                base[k] = str(d[k]).strip()
        p = d.get("poll")
        if isinstance(p, dict) and all(str(p.get(k, "")).strip() for k in "qab"):
            base["poll"] = {k: str(p[k]).strip() for k in "qab"}
    except Exception as e:  # noqa: BLE001
        print(f"  Original: la IA no respondió ({type(e).__name__}); uso frases genéricas.", flush=True)
    base["context"], base["outro"] = base["context"][:100], base["outro"][:70]
    return base


def tts(text, out, voice):
    """Voz narradora. 1º edge-tts (voces dominicanas gratis, necesita internet), 2º espeak-ng, si no, sin voz (None)."""
    text = re.sub(r"[^\w\s¿?¡!,.:;'\-áéíóúüñÁÉÍÓÚÜÑ]", " ", text).strip()
    if not text:
        return None
    out = Path(out)
    try:
        import asyncio
        import edge_tts

        async def go():
            await edge_tts.Communicate(text, voice, rate="+6%").save(str(out))
        asyncio.run(go())
        if out.exists() and out.stat().st_size > 500:
            return out
    except Exception as e:  # noqa: BLE001
        print(f"  Voz: edge-tts no disponible ({type(e).__name__}); pruebo espeak-ng.", flush=True)
    if shutil.which("espeak-ng"):
        wav = out.with_suffix(".wav")
        r = subprocess.run(["espeak-ng", "-v", "es", "-s", "160", "-w", str(wav), text], capture_output=True)
        if r.returncode == 0 and wav.exists():
            return wav
    return None


def _dur(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# ---------------------------------------------------------------- tarjetas y piezas

def _esc(t):
    t = "".join(ch for ch in t if ord(ch) < 0x2190).strip()     # las tarjetas no dibujan emojis
    return t.replace("{", "(").replace("}", ")").replace("\\", "/").replace("\n", "\\N")


_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Big,Montserrat,72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,4,0,5,90,90,0,1
Style: Small,Montserrat,42,&H0000E0FF,&H0000E0FF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,3,0,8,90,90,380,1
Style: Meter,Montserrat,38,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,1,0,1,4,0,9,0,60,150,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""


def make_card(text, small, min_dur, out, workdir, voice=None, color="0x101820"):
    """Tarjeta vertical 1080x1920. Si hay voz, dura lo que dure la voz (+0.5 s)."""
    workdir = Path(workdir)
    ass = workdir / (Path(out).stem + "_card.ass")
    d = max(min_dur, _dur(voice) + 0.5) if voice else min_dur
    ass.write_text(_HEAD + f"Dialogue: 0,0:00:00.00,0:00:{d + 1:05.2f},Big,,0,0,0,,{{\\fad(250,200)}}{_esc(text)}\n"
                   + (f"Dialogue: 0,0:00:00.00,0:00:{d + 1:05.2f},Small,,0,0,0,,{_esc(small)}\n" if small else ""),
                   encoding="utf-8")
    vf = (f"drawbox=x=0:y=0:w=iw:h=16:color=0xFFE000:t=fill,drawbox=x=0:y=ih-16:w=iw:h=16:color=0xFFE000:t=fill,"
          f"subtitles={ass.name},format=yuv420p")
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={FPS}:d={d:.2f}"]
    if voice:
        cmd += ["-i", str(Path(voice).resolve()), "-filter_complex",
                f"[0:v]{vf}[v];[1:a]aresample=48000,aformat=channel_layouts=stereo,apad[a]", "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-vf", vf]
    cmd += ["-t", f"{d:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
            "-shortest", str(Path(out).resolve())]
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("tarjeta falló: " + r.stderr[-400:])
    return Path(out)


def _meter_ass(pct, path):
    """Dramómetro: etiqueta + barra que se llena, arriba a la derecha, los primeros 4 s del clip."""
    pct = int(min(99, max(35, pct)))
    x0, x1, y0, y1 = 690, 1020, 132, 156
    xf = x0 + (x1 - x0) * pct // 100
    box = lambda c, xa, xb: (f"{{\\an7\\pos(0,0)\\p1\\c&H{c}&\\bord0\\shad0}}m {xa} {y0} l {xb} {y0} {xb} {y1} {xa} {y1}{{\\p0}}")
    t = "0:00:00.30"
    e = "0:00:04.20"
    Path(path).write_text(_HEAD
                          + f"Dialogue: 1,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}DRAMOMETRO {pct}%\n"
                          + f"Dialogue: 0,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}{box('303030', x0, x1)}\n"
                          + f"Dialogue: 2,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}{box('1E5AFF', x0, xf)}\n", encoding="utf-8")


def concat(parts, out, workdir, vf_extra=None):
    """Une videos 1080x1920 (con audio) en uno; vf_extra = {índice: filtro de video extra para esa pieza}."""
    vf_extra = vf_extra or {}
    ins, fl = [], []
    for i, p in enumerate(parts):
        ins += ["-i", str(Path(p).resolve())]
        extra = (vf_extra[i] + ",") if i in vf_extra else ""
        fl.append(f"[{i}:v]fps={FPS},scale={W}:{H},setsar=1,{extra}format=yuv420p[v{i}];"
                  f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]")
    n = len(parts)
    graph = ";".join(fl) + ";" + "".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    cmd = ["ffmpeg", "-y", *ins, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", config.CLIP_PRESET, "-crf", str(config.CLIP_CRF), "-profile:v", "high",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(Path(out).resolve())]
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("unir falló: " + r.stderr[-400:])
    return Path(out)


def wrap_clip(clip, ex, out, workdir, cfg, score=75):
    """contexto (con voz) + clip (con dramómetro) + cierre (encuesta A/B, con voz) -> out."""
    workdir, stem = Path(workdir), Path(out).stem
    voice = (lambda txt, tag: tts(txt, workdir / f"{stem}_{tag}.mp3", cfg["voice"])) if cfg["narrate"] else (lambda *a: None)
    temp = []
    try:
        v1 = voice(ex["context"], "v1")
        a = make_card(ex["context"], cfg["show"], 2.5, workdir / f"{stem}_in.mp4", workdir, v1)
        if cfg["poll"] and ex.get("poll"):
            p = ex["poll"]
            end_text, end_small = f"{p['q']}\n\nA) {p['a']}\nB) {p['b']}", "COMENTA A O B"
            v2 = voice(f"{p['q']} Comenta A o B.", "v2")
        else:
            end_text, end_small = ex["outro"], cfg["page"]
            v2 = voice(ex["outro"], "v2")
        b = make_card(end_text, end_small, 2.8, workdir / f"{stem}_out.mp4", workdir, v2)
        temp += [a, b, v1, v2]
        extra = {}
        if cfg["meter"]:
            mass = workdir / f"{stem}_meter.ass"
            _meter_ass(score, mass)
            extra[1] = f"subtitles={mass.name}"
        concat([a, clip, b], out, workdir, extra)
    finally:
        for p in temp:
            if p:
                Path(p).unlink(missing_ok=True)
    return Path(out)


def compilation(items, head, out, workdir, cfg):
    """TOP con cuenta regresiva. items = [(título, archivo)] ya en el orden de aparición (#N … #1)."""
    workdir = Path(workdir)
    voice = (lambda txt, tag: tts(txt, workdir / f"comp_{tag}.mp3", cfg["voice"])) if cfg["narrate"] else (lambda *a: None)
    parts, temp = [], []
    try:
        v = voice(f"{head}. Los mejores momentos de {cfg['show']}.", "head")
        t = make_card(head, cfg["show"], 2.5, workdir / "comp_title.mp4", workdir, v)
        parts.append(t); temp += [t, v]
        n = len(items)
        for i, (title, path) in enumerate(items):
            k = make_card(f"#{n - i}\n{title[:60]}", "", 1.6, workdir / f"comp_{i}.mp4", workdir)
            parts += [k, path]; temp.append(k)
        concat(parts, out, workdir)
    finally:
        for p in temp:
            if p:
                Path(p).unlink(missing_ok=True)
    return Path(out)


def description(m, ex, cfg):
    """Descripción del post: tu punto de vista + (encuesta) + crédito de permiso + hashtags."""
    bits = [ex.get("caption") or m.get("description") or ""]
    if ex.get("poll") and cfg["poll"]:
        bits.append(f"{ex['poll']['q']} A) {ex['poll']['a']}  B) {ex['poll']['b']}  Comenta tu respuesta")
    if cfg.get("credit"):
        bits.append(cfg["credit"])
    tags = " ".join(m.get("hashtags") or [])
    return "\n\n".join(b for b in bits if b) + (f"\n\n{tags}" if tags else "")
