"""Modo Original (sin mostrar la cara ni hablar tú): convierte un corte en un clip con aporte propio."""
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

def load(workdir=None, content_type="podcast"):
    cfg = dict(DEFAULTS)
    try:
        import db
        raw = db.sb.storage.from_("uploads").download("brand/original.json")
        saved = json.loads(raw.decode("utf-8")) if raw else {}
        cfg.update({k: saved[k] for k in DEFAULTS if k in saved})
    except Exception:
        pass
    cfg["top_n"] = int(min(10, max(3, int(cfg.get("top_n") or 5))))
    return cfg

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
    except Exception as e:
        print(f"  Original: la IA no respondió ({type(e).__name__}); uso frases genéricas.", flush=True)
    base["context"], base["outro"] = base["context"][:100], base["outro"][:70]
    return base

def tts(text, out, voice):
    text = re.sub(r"[^\w\s¿?¡!,.:;'\-áéíóúüñÁÉÍÓÚÜÑ]", " ", text).strip()
    if not text:
        return None
    out = Path(out)
    try:
        import asyncio
        import edge_tts

        async def go():
            await edge_tts.Communicate(text, voice, rate="+10%").save(str(out))
        asyncio.run(go())
        if out.exists() and out.stat().st_size > 500:
            return out
    except Exception as e:
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

def _esc(t):
    t = "".join(ch for ch in t if ord(ch) < 0x2190).strip()
    return t.replace("{", "(").replace("}", ")").replace("\\", "/").replace("\n", "\\N")

_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Big,Montserrat,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,2,5,80,80,0,1
Style: Small,Montserrat,54,&H0000E0FF,&H0000E0FF,&H00000000,&H00000000,-1,0,0,0,100,100,3,0,1,4,0,8,90,90,330,1
Style: Meter,Montserrat,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,5,0,8,0,0,125,1
Style: Intro,Montserrat,60,&H00FFFFFF,&H00FFFFFF,&H78000000,&H00000000,-1,0,0,0,100,100,0,0,3,20,0,8,90,90,330,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

POP = "{\\fad(250,200)\\fscx85\\fscy85\\t(0,320,\\fscx100\\fscy100)}"


def grab_frame(clip, at, out):
    """Un cuadro del clip (at = 'first' o 'last') para usarlo de fondo de las tarjetas. Devuelve la ruta o None."""
    clip = Path(clip)
    d = _dur(clip)
    t = 0.0 if at == "first" else max(0.0, d - 0.3)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(clip.resolve()),
                        "-frames:v", "1", str(Path(out).resolve())], capture_output=True)
    return Path(out) if r.returncode == 0 and Path(out).exists() else None


def make_card(text, small, min_dur, out, workdir, voice=None, color="0x101820", bg=None):
    """Tarjeta de texto. Si pasas bg (imagen), el fondo es ese cuadro borroso, oscurecido y con un movimiento lento,
    para que no se vea una pantalla muerta; sin bg queda el color plano de siempre."""
    workdir = Path(workdir)
    ass = workdir / (Path(out).stem + "_card.ass")
    d = max(min_dur, _dur(voice) + 0.5) if voice else min_dur
    ass.write_text(_HEAD + f"Dialogue: 0,0:00:00.00,0:00:{d + 1:05.2f},Big,,0,0,0,,{POP}{_esc(text)}\n"
                   + (f"Dialogue: 0,0:00:00.00,0:00:{d + 1:05.2f},Small,,0,0,0,,{{\\fad(250,200)}}{_esc(small)}\n" if small else ""),
                   encoding="utf-8")
    bars = ("drawbox=x=0:y=0:w=iw:h=16:color=0xFFE000:t=fill,drawbox=x=0:y=ih-16:w=iw:h=16:color=0xFFE000:t=fill,"
            f"subtitles={ass.name},format=yuv420p")
    use_bg = bool(bg and Path(bg).exists())
    if use_bg:
        cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(Path(bg).resolve())]
        # imagen más grande que el cuadro + recorte que se desliza despacio = movimiento sin zoompan (que es lento)
        pre = (f"scale={int(W * 1.12)}:{int(H * 1.12)}:force_original_aspect_ratio=increase,"
               f"crop={W}:{H}:x='(iw-ow)*min(1,t/{max(d, 1):.2f})':y='(ih-oh)/2',boxblur=22:3,eq=brightness=-0.10:saturation=0.9,")
    else:
        cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={FPS}:d={d:.2f}"]
        pre = ""
    vf = pre + bars
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

def _meter_color(pct):
    """Color BGR de la barra: amarillo (tranquilo), naranja (tenso), rojo (explosivo)."""
    return "00E0FF" if pct < 50 else ("1E8CFF" if pct < 75 else "1E1EFF")

def _meter_ass(pct, path, intro=None, show_meter=True):
    """Dramómetro (si show_meter) y, en apertura directa (INTRO_MODE=cold), el texto de contexto encima de los primeros segundos."""
    pct = int(min(99, max(35, pct)))
    x0, x1, y0, y1 = 250, 830, 200, 246          # 580 x 46 px, centrada, debajo de la zona de la barra del teléfono
    xf = x0 + (x1 - x0) * pct // 100
    box = lambda c, xa, xb: (f"{{\\an7\\pos(0,0)\\p1\\c&H{c}&\\bord0\\shad0}}m {xa} {y0} l {xb} {y0} {xb} {y1} {xa} {y1}{{\\p0}}")
    t = "0:00:00.30"
    e = "0:00:05.00"
    ev = ""
    if show_meter:
        ev += (f"Dialogue: 1,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}DRAMÓMETRO {pct}%\n"
               f"Dialogue: 0,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}{box('303030', x0 - 6, x1 + 6)}\n"
               f"Dialogue: 2,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}{box(_meter_color(pct), x0, xf)}\n")
    if intro:
        ev += f"Dialogue: 3,0:00:00.20,0:00:03.40,Intro,,0,0,0,,{POP}{_esc(intro)}\n"
    Path(path).write_text(_HEAD + ev, encoding="utf-8")

def concat(parts, out, workdir, vf_extra=None):
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
    """Envuelve el clip con intro + cierre. INTRO_MODE=card (por defecto): tarjeta narrada antes del clip.
    INTRO_MODE=cold: el clip arranca de inmediato y el texto de contexto sale encima de los primeros 3 s (mejor retención,
    pero sin la voz narradora de la intro; el cierre sigue narrado)."""
    workdir, stem = Path(workdir), Path(out).stem
    cold = config.INTRO_MODE == "cold"
    voice = (lambda txt, tag: tts(txt, workdir / f"{stem}_{tag}.mp3", cfg["voice"])) if cfg["narrate"] else (lambda *a: None)
    temp = []
    try:
        parts, extra = [], {}
        bg_out = grab_frame(clip, "last", workdir / f"{stem}_bg_out.png")
        temp.append(bg_out)
        if cold:
            parts.append(clip)
        else:
            v1 = voice(ex["context"], "v1")
            bg_in = grab_frame(clip, "first", workdir / f"{stem}_bg_in.png")
            temp += [bg_in, v1]
            a = make_card(ex["context"], cfg["show"], 2.2, workdir / f"{stem}_in.mp4", workdir, v1, bg=bg_in)
            temp.append(a)
            parts += [a, clip]
        if cfg["poll"] and ex.get("poll"):
            p = ex["poll"]
            end_text, end_small = f"{p['q']}\n\nA) {p['a']}\nB) {p['b']}", "COMENTA A O B"
            v2 = voice(f"{p['q']} Comenta A o B.", "v2")
        else:
            end_text, end_small = ex["outro"], cfg["page"]
            v2 = voice(ex["outro"], "v2")
        b = make_card(end_text, end_small, 2.8, workdir / f"{stem}_out.mp4", workdir, v2, bg=bg_out)
        temp += [b, v2]
        parts.append(b)
        if cfg["meter"] or cold:
            mass = workdir / f"{stem}_meter.ass"
            _meter_ass(score, mass, intro=ex["context"] if cold else None, show_meter=bool(cfg["meter"]))
            extra[0 if cold else 1] = f"subtitles={mass.name}"
            temp.append(mass)
        concat(parts, out, workdir, extra)
    finally:
        for p in temp:
            if p:
                Path(p).unlink(missing_ok=True)
    return Path(out)

def compilation(items, head, out, workdir, cfg):
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
    bits = [ex.get("caption") or m.get("description") or ""]
    if ex.get("poll") and cfg["poll"]:
        bits.append(f"{ex['poll']['q']} A) {ex['poll']['a']}  B) {ex['poll']['b']}  Comenta tu respuesta")
    if cfg.get("credit"):
        bits.append(cfg["credit"])
    tags = " ".join(m.get("hashtags") or [])
    return "\n\n".join(b for b in bits if b) + (f"\n\n{tags}" if tags else "")
