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
    "intro": config.INTRO_MODE,          # "cold" = el clip arranca ya con el gancho encima | "card" = tarjeta narrada antes
    "smart_start": config.SMART_START,   # empezar en la primera frase fuerte (lo lee main.py)
}

PROMPT = """Eres el editor de una página de clips de "{show}" para Facebook. Español dominicano natural, sin groserías, sin insultos. Piensa como un editor que quiere que la gente NO pueda dejar de ver el clip. Usa jerga dominicana cuando encaje (klk, vaina, tíguere, chercha, jevi, pariguayo, colmadito, manin). Sé creativo, original y atrevido. Los titulos deben generar curiosidad extrema. El contexto debe ser intrigante y no revelar el final. La encuesta debe dividir opiniones. El caption debe invitar a comentar. El dramómetro debe ser emocionante. Los bandos deben ser claros y opuestos. Sé creativo y original.
Del fragmento saca texto ORIGINAL (no copies frases largas textuales). Devuelve:
- context: 1 frase (máx 90 caracteres) que ponga en situación a quien no vio el programa SIN contar el final ("Antes de esto, ..."), legible en voz alta. Debe generar curiosidad, no revelar el desenlace. Usa palabras de drama/emoción cuando el clip las tiene.
- outro: 1 pregunta corta (máx 60 caracteres) que divida opiniones y dé ganas de comentar. Evita frases vacías ("¿Qué te parece?"). Que sea polémica pero sin insultos.
- poll: {{"q":"pregunta de 'quién tiene la razón' (máx 50 car.)","a":"bando A (máx 22 car.)","b":"bando B (máx 22 car.)"}}. Los dos bandos deben ser claros, opuestos y defendibles (nombres de personas o posturas), sin insultos.
- caption: descripción del post, 2 frases con punto de vista propio, sin spoilear el final, que cierre invitando a comentar.
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
    cfg["intro"] = cfg.get("intro") if cfg.get("intro") in ("cold", "card") else "cold"
    cfg["smart_start"] = bool(cfg.get("smart_start", True))
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
    # Plan B: espeak-ng (offline, voz robótica pero siempre disponible)
    if shutil.which("espeak-ng"):
        wav = out.with_suffix(".wav")
        r = subprocess.run(["espeak-ng", "-v", "es", "-s", "150", "-p", "40", "-w", str(wav), text], capture_output=True)
        if r.returncode == 0 and wav.exists() and wav.stat().st_size > 500:
            return wav
    # Plan C: pyttsx3 (offline, si está instalado)
    try:
        import pyttsx3
        wav = out.with_suffix(".wav")
        eng = pyttsx3.init()
        eng.setProperty("rate", 150)
        eng.save_to_file(text, str(wav))
        eng.runAndWait()
        if wav.exists() and wav.stat().st_size > 500:
            return wav
    except Exception:  # noqa: BLE001
        pass
    # Plan D: gTTS (online, voz natural; necesita internet)
    try:
        from gtts import gTTS
        mp3 = out.with_suffix(".mp3")
        gTTS(text=text, lang="es").save(str(mp3))
        if mp3.exists() and mp3.stat().st_size > 500:
            return mp3
    except Exception:  # noqa: BLE001
        pass
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
Style: Big,Montserrat,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,9,3,5,80,80,0,1
Style: Small,Montserrat,58,&H0000E0FF,&H0000E0FF,&H00000000,&H00000000,-1,0,0,0,100,100,3,0,1,5,0,8,90,90,330,1
Style: Meter,Montserrat,60,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,7,0,8,0,0,125,1
Style: Intro,Montserrat,50,&H00FFFFFF,&H00FFFFFF,&H78000000,&H00000000,-1,0,0,0,100,100,0,0,3,16,0,8,70,70,560,1
Style: Q,Montserrat,92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,2,8,80,80,430,1
Style: Letter,Montserrat,150,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,0,5,0,0,0,1
Style: Opt,Montserrat,64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,4,0,0,0,1
Style: Cta,Montserrat,70,&H0000E0FF,&H0000E0FF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,6,2,8,60,60,1290,1
Style: Page,Montserrat,48,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,5,0,8,60,60,1420,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""

POP = "{\\fad(180,160)\\fscx75\\fscy75\\t(0,260,\\fscx100\\fscy100)\\blur0.6\\bord1}"


def grab_frame(clip, at, out):
    """Un cuadro del clip (at = 'first' o 'last') para usarlo de fondo de las tarjetas. Devuelve la ruta o None."""
    clip = Path(clip)
    d = _dur(clip)
    t = 0.0 if at == "first" else max(0.0, d - 0.3)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(clip.resolve()),
                        "-frames:v", "1", str(Path(out).resolve())], capture_output=True)
    return Path(out) if r.returncode == 0 and Path(out).exists() else None


def _render_card(ass_text, d, out, workdir, voice=None, color="0x101820", bg=None):
    """Convierte un guion ASS en una tarjeta de video de `d` segundos (fondo: cuadro borroso con movimiento, o color plano)."""
    workdir = Path(workdir)
    ass = workdir / (Path(out).stem + "_card.ass")
    ass.write_text(ass_text, encoding="utf-8")
    bars = (f"drawbox=x=0:y=0:w=iw:h=16:color=0xFFE000:t=fill,drawbox=x=0:y=ih-16:w=iw:h=16:color=0xFFE000:t=fill,"
            f"subtitles={ass.name},format=yuv420p")
    use_bg = bool(bg and Path(bg).exists())
    if use_bg:
        cmd = ["ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(Path(bg).resolve())]
        # imagen más grande que el cuadro + recorte que se desliza despacio = movimiento sin zoompan (que es lento)
        pre = (f"scale={int(W * 1.12)}:{int(H * 1.12)}:force_original_aspect_ratio=increase,"
               f"crop={W}:{H}:x='(iw-ow)*min(1,t/{max(d, 1):.2f})':y='(ih-oh)/2',boxblur=22:3,eq=brightness=-0.16:saturation=0.9,")
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


def make_card(text, small, min_dur, out, workdir, voice=None, color="0x101820", bg=None):
    """Tarjeta de texto. Si pasas bg (imagen), el fondo es ese cuadro borroso, oscurecido y con un movimiento lento,
    para que no se vea una pantalla muerta; sin bg queda el color plano de siempre."""
    d = max(min_dur, _dur(voice) + 0.7) if voice else min_dur
    ass = (_HEAD + f"Dialogue: 0,0:00:00.00,0:00:{d + 1:05.2f},Big,,0,0,0,,{POP}{_esc(text)}\n"
           + (f"Dialogue: 0,0:00:00.00,0:00:{d + 1:05.2f},Small,,0,0,0,,{{\\fad(250,200)}}{_esc(small)}\n" if small else ""))
    return _render_card(ass, d, out, workdir, voice, color, bg)


# colores de la encuesta (ASS usa BGR): A = azul, B = rojo
POLL_A, POLL_B = "FF781E", "3C3CFF"


def _ts(sec):
    sec = max(0.0, float(sec))
    return f"0:{int(sec // 60):02d}:{sec % 60:05.2f}"


def _poll_ass(p, page, d):
    """Tarjeta de encuesta: pregunta arriba y dos paneles de color (A azul, B rojo) que entran deslizando; abajo, a comentar."""
    end = _ts(d + 1)
    x0, x1 = 90, 990
    out = _HEAD
    out += f"Dialogue: 2,0:00:00.00,{end},Q,,0,0,0,,{POP}{_esc(p['q'])}\n"
    for k, (letter, key, col, y0, y1, t_in) in enumerate((("A", "a", POLL_A, 700, 920, 350), ("B", "b", POLL_B, 980, 1200, 700))):
        yc = (y0 + y1) // 2
        opt = _esc(p[key])
        fs = 60 if len(opt) <= 14 else (52 if len(opt) <= 18 else 46)
        out += (f"Dialogue: 0,0:00:00.00,{end},Opt,,0,0,0,,{{\\an7\\move(-1080,0,0,0,{t_in},{t_in + 320})\\p1\\c&H{col}&\\3c&H000000&\\bord4\\shad0}}"
                f"m {x0} {y0} l {x1} {y0} {x1} {y1} {x0} {y1}{{\\p0}}\n")
        out += f"Dialogue: 1,{_ts((t_in + 250) / 1000)},{end},Letter,,0,0,0,,{{\\pos(210,{yc})\\fad(120,0)}}{letter}\n"
        out += f"Dialogue: 1,{_ts((t_in + 250) / 1000)},{end},Opt,,0,0,0,,{{\\an4\\pos(330,{yc})\\fs{fs}\\q2\\fad(120,0)}}{opt}\n"
    out += f"Dialogue: 1,{_ts(1.0)},{end},Cta,,0,0,0,,{{\\fad(200,0)\\fscx90\\fscy90\\t(0,300,\\fscx100\\fscy100)}}COMENTA A O B\n"
    if page:
        out += f"Dialogue: 1,{_ts(1.2)},{end},Page,,0,0,0,,{{\\fad(250,0)}}{_esc(page)}\n"
    return out


def make_poll_card(p, page, min_dur, out, workdir, voice=None, bg=None):
    d = max(min_dur, _dur(voice) + 0.7) if voice else min_dur
    return _render_card(_poll_ass(p, page, d), d, out, workdir, voice, "0x101820", bg)


def _meter_color(pct):
    """Color BGR de la barra: amarillo (tranquilo), naranja (tenso), rojo (explosivo)."""
    return "00E0FF" if pct < 50 else ("1E8CFF" if pct < 75 else "1E1EFF")


def _meter_level(pct):
    return "CALENTITO" if pct < 50 else ("TENSO" if pct < 75 else "EXPLOSIVO")


def _meter_ass(pct, path, intro=None, show_meter=True):
    """Dramómetro (la barra se llena en ~1 s) y, en apertura directa (INTRO_MODE=cold), el texto de contexto debajo del gancho."""
    pct = int(min(99, max(35, pct)))
    x0, x1, y0, y1 = 220, 860, 190, 250          # 640 x 60 px, más ancha y alta, más visible en móvil
    xf = x0 + (x1 - x0) * pct // 100
    box = lambda c, xa, xb: (f"{{\\an7\\pos(0,0)\\p1\\c&H{c}&\\bord0\\shad0}}m {xa} {y0} l {xb} {y0} {xb} {y1} {xa} {y1}{{\\p0}}")
    t = "0:00:00.30"
    e = "0:00:05.00"
    ev = ""
    if show_meter:
        grow = f"\\clip({x0},{y0},{x0},{y1})\\t(0,1100,\\clip({x0},{y0},{xf},{y1}))"
        fill = (f"{{\\an7\\pos(0,0)\\p1\\c&H{_meter_color(pct)}&\\bord0\\shad0{grow}}}"
                f"m {x0} {y0} l {xf} {y0} {xf} {y1} {x0} {y1}{{\\p0}}")
        ev += (f"Dialogue: 1,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}DRAMÓMETRO {pct}% · NIVEL MÁXIMO {_meter_level(pct)}\n"
               f"Dialogue: 0,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}{box('303030', x0 - 6, x1 + 6)}\n"
               f"Dialogue: 2,{t},{e},Meter,,0,0,0,,{{\\fad(200,300)}}{fill}\n")
    if intro:   # sale un instante después del gancho (que ya está arriba desde el primer cuadro) y debajo de él
        ev += f"Dialogue: 3,0:00:00.90,0:00:04.60,Intro,,0,0,0,,{POP}{_esc(intro)}\n"
    Path(path).write_text(_HEAD + ev, encoding="utf-8")


def size_cap(total_sec):
    """Bitrate máximo de video (bits/s) para que un archivo de `total_sec` segundos pese a lo más CLIP_MAX_MB."""
    return int(min(10_000_000, max(1_000_000, config.CLIP_MAX_MB * 1_000_000 * 8 / max(total_sec, 1.0) - 192_000)))


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
    # Tope de tamaño: el resultado final NUNCA pasa de CLIP_MAX_MB (Supabase rechaza archivos de 50 MB o más).
    cap = size_cap(sum(_dur(p) for p in parts) or 60.0)
    cmd = ["ffmpeg", "-y", *ins, "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", config.CLIP_PRESET, "-crf", str(config.CLIP_CRF), "-maxrate", str(cap), "-bufsize", str(cap * 2),
           "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(Path(out).resolve())]
    r = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("unir falló: " + r.stderr[-400:])
    return Path(out)


def wrap_clip(clip, ex, out, workdir, cfg, score=75):
    """Envuelve el clip. intro="cold" (por defecto): el clip arranca en el primer cuadro con el gancho encima y, un instante después,
    el contexto debajo; no hay nada antes del video (la gente decide en 2 s). intro="card": tarjeta narrada antes del clip.
    Al final: encuesta A/B con paneles de color (o la pregunta de cierre), narrada."""
    workdir, stem = Path(workdir), Path(out).stem
    cold = (cfg.get("intro") or config.INTRO_MODE) == "cold"
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
            v2 = voice(f"{p['q']} Comenta A o B.", "v2")
            b = make_poll_card(p, cfg.get("page", ""), 2.8, workdir / f"{stem}_out.mp4", workdir, v2, bg=bg_out)
        else:
            v2 = voice(ex["outro"], "v2")
            b = make_card(ex["outro"], cfg["page"], 2.8, workdir / f"{stem}_out.mp4", workdir, v2, bg=bg_out)
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
    """TOP con cuenta regresiva. Cada tarjeta lleva de fondo un cuadro real del clip (no una pantalla muerta)."""
    workdir = Path(workdir)
    voice = (lambda txt, tag: tts(txt, workdir / f"comp_{tag}.mp3", cfg["voice"])) if cfg["narrate"] else (lambda *a: None)
    parts, temp = [], []
    try:
        v = voice(f"{head}. Los mejores momentos de {cfg['show']}.", "head")
        bg0 = grab_frame(items[-1][1], "first", workdir / "comp_bg_head.png") if items else None
        t = make_card(head, cfg["show"], 2.5, workdir / "comp_title.mp4", workdir, v, bg=bg0)
        parts.append(t); temp += [t, v, bg0]
        n = len(items)
        for i, (title, path) in enumerate(items):
            bg = grab_frame(path, "first", workdir / f"comp_bg_{i}.png")
            k = make_card(f"#{n - i}\n{title[:60]}", "", 1.6, workdir / f"comp_{i}.mp4", workdir, bg=bg)
            parts += [k, path]; temp += [k, bg]
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
