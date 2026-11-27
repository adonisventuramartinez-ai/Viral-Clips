"""Parte 3: verificación de candidatos con imágenes.

Para los mejores candidatos saca 2 a 5 fotogramas del tramo (por defecto 3), se los manda a un modelo con visión (Groq, Gemini o Claude)
y ajusta el puntaje: si en pantalla hay un menú, una pantalla de carga, negro o "no pasa nada", el clip baja; si se ve la acción, sube un poco.
Es un EXTRA: si no hay modelo con visión, no hay cupo o algo falla, los puntajes quedan como estaban.
"""
import json
import subprocess
from pathlib import Path

import config
import llm
import profiles

PROMPT = """Eres editor de clips virales ({kind}). Te paso {n} fotogramas de UN clip candidato, en orden (principio, medio y final).
Título propuesto: "{title}"
Lo que se dice en el clip: "{text}"
{guide_short}

Mira las imágenes y responde SOLO con JSON:
{{"verdict":"strong" | "ok" | "weak" | "bad","score":<0-100 qué tan buen clip se ve>,"seen":"qué se ve en pantalla, 1 frase","problem":"si es weak/bad, por qué (menú, pantalla de carga, negro, nada pasa, mapa, inventario, imagen congelada...)"}}
- "strong": se ve acción, drama o algo llamativo que respalda el título.
- "ok": se ve normal, sin problema.
- "weak": poco interesante o no se ve lo que dice el título.
- "bad": menú, carga, pantalla negra/congelada, o nada que ver con el clip."""


def frames(video: Path, start: float, end: float, n=3, width=512):
    """n fotogramas JPEG (bytes) repartidos dentro de [start, end]. Lista vacía si falla."""
    n = max(1, int(n))
    dur = max(0.5, end - start)
    out = []
    for k in range(n):
        t = start + dur * (0.12 + 0.76 * (k / max(1, n - 1) if n > 1 else 0.5))
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
               "-vf", f"scale={width}:-2", "-q:v", "5", "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=60)
        except Exception:  # noqa: BLE001
            continue
        if r.returncode == 0 and len(r.stdout) > 500:
            out.append(r.stdout)
    return out


def _parse(txt):
    a, b = txt.find("{"), txt.rfind("}")
    if a < 0 or b < 0:
        return None
    try:
        d = json.loads(txt[a: b + 1])
    except json.JSONDecodeError:
        return None
    return d if isinstance(d, dict) and d.get("verdict") in ("strong", "ok", "weak", "bad") else None


def enabled(prof):
    """¿Corresponde verificar con imágenes para este perfil? (VERIFY_IMAGES: auto / 1 / 0)."""
    mode = config.VERIFY_IMAGES
    if mode in ("0", "false", "no", "off"):
        return False
    if mode in ("1", "true", "yes", "on"):
        return llm.vision_available()
    return bool(prof.get("verify")) and llm.vision_available()


def adjust(m, d):
    """Aplica el veredicto al puntaje del momento (función pura, fácil de probar)."""
    try:
        vis = int(max(0, min(100, float(d.get("score", 50)))))
    except (TypeError, ValueError):
        vis = 50
    verdict = d["verdict"]
    before = m["score"]
    score = round(0.75 * before + 0.25 * vis)
    if verdict == "strong":
        score = min(100, score + 4)
    elif verdict == "weak":
        score = min(score, before - 8)
    elif verdict == "bad":
        score = min(score, 35)
    m["score"] = int(max(0, min(100, score)))
    m["vision"] = verdict
    note = {"strong": "👁 se ve la acción", "ok": "", "weak": "👁 poco que ver", "bad": "👁 " + str(d.get("problem") or "sin imagen útil")[:60]}[verdict]
    if note:
        m["reason"] = (m.get("reason", "") + " " + note).strip()
    return m


def verify(cands, video, prof, text_of, top=None, n_frames=None):
    """Revisa con imágenes los `top` mejores candidatos (por puntaje) y ajusta su puntaje. Devuelve cuántos revisó."""
    if not cands or video is None or not enabled(prof):
        return 0
    top = top or config.VERIFY_TOP
    n_frames = n_frames or config.VERIFY_FRAMES
    guide = str(prof.get("guide", ""))
    guide_short = ("Contexto: " + guide[:350]) if guide else ""
    done = 0
    for m in sorted(cands, key=lambda x: x["score"], reverse=True)[:top]:
        try:
            imgs = frames(video, m["start"], m["end"], n_frames)
            if len(imgs) < 2:
                continue
            prompt = PROMPT.format(kind=prof.get("kind", "un video"), n=len(imgs), title=m["title"],
                                   text=(text_of(m, 280) or "(sin voz)").replace('"', "'"), guide_short=guide_short)
            d = llm.ask_vision(prompt, imgs, check=_parse)
        except llm.AllBusy as e:
            print(f"  Verificación con imágenes: paro aquí ({str(e)[:90]}). Los demás quedan como estaban.", flush=True)
            break
        except Exception as e:  # noqa: BLE001  (es un extra: nunca debe tumbar el trabajo)
            print(f"  Verificación con imágenes: no pude revisar '{m['title'][:30]}' ({type(e).__name__})", flush=True)
            continue
        adjust(m, d)
        done += 1
    if done:
        bad = sum(1 for m in cands if m.get("vision") in ("weak", "bad"))
        print(f"  Verificación con imágenes: revisé {done} candidato(s), {bad} bajaron de puntaje", flush=True)
    return done
