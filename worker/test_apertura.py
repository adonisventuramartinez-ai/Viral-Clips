"""Apertura que engancha: gancho afilado + transformar en frío + voz sobre el video."""
import subprocess
import tempfile
from pathlib import Path

import config
import hook
import original

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


def mk(text, step=0.5):
    out, t = [], 0.0
    for w in text.split():
        out.append({"w": w, "start": round(t, 2), "end": round(t + step * 0.8, 2)})
        t += step
    return out


# --- Transformar arranca en frío (sin tarjeta que regale 2 s)
check("transformar arranca en frío", config.TRANSFORM_INTRO == "cold")

# --- El gancho plano se vuelve duda; el que ya impacta no se toca
check("gancho con impacto intacto", hook.sharpen("Le dijo la verdad en su cara") == "Le dijo la verdad en su cara")
check("gancho plano se vuelve pregunta", hook.sharpen("Eso pasó ayer en la casa").startswith("¿"))
check("gancho genérico no se adorna", hook.sharpen("MIRA ESTO") == "MIRA ESTO")
check("pregunta sigue pregunta", hook.sharpen("¿Quién se atrevió?") == "¿Quién se atrevió?")

# --- best_hook sigue firme con los casos clásicos
words = mk("Bueno hola. Le dijo la verdad delante de todos los invitados. Y se quedó callada.")
end = words[-1]["end"] + 0.1
check("best_hook elige gancho concreto", "verdad" in hook.best_hook("¡MIRA ESTO!", "Título", words, 0.0, end).lower())
check("best_hook sin datos usa título", hook.best_hook("", "La pelea del año", [], 0.0, 30.0) == "La pelea del año")

# --- Contexto: nunca el genérico de siempre
ctx = hook.opening_context({"context": "Momento clave de Show"}, words, 0.0)
check("contexto genérico se reemplaza", ctx.startswith("Antes de esto") and "momento clave" not in ctx.lower())
check("contexto bueno se conserva",
      hook.opening_context({"context": "Antes de esto, nadie sabía la verdad"}, [], 0.0) ==
      "Antes de esto, nadie sabía la verdad")

# --- La IA puede proponer gancho y original.extras lo valida
import llm
old_ask = llm.ask
try:
    llm.ask = lambda prompt, check=None: {"context": "Antes de esto, todo cambió", "hook": "¿Qué dijo que dejó a todos callados?",
                                          "outro": "¿Quién tenía razón?", "poll": {"q": "¿Quién gana?", "a": "A", "b": "B"},
                                          "caption": "Mira cómo termina"}
    ex = original.extras("texto", original.load())
    check("extras trae gancho de la IA", ex["hook"] == "¿Qué dijo que dejó a todos callados?")
    llm.ask = lambda prompt, check=None: {"context": "x", "hook": "MIRA ESTO", "outro": "y"}
    ex2 = original.extras("texto", original.load())
    check("extras descarta gancho vago", ex2["hook"] == "")
finally:
    llm.ask = old_ask

# --- El ASS de apertura quema el gancho ARRIBA desde el primer cuadro
with tempfile.TemporaryDirectory() as td:
    ass = Path(td) / "open.ass"
    original._meter_ass(80, ass, intro="Antes de esto, pasó algo", show_meter=True, hook="¿QUÉ DIJO?")
    txt = ass.read_text(encoding="utf-8")
    check("ASS trae estilo de apertura", "Style: Open," in txt)
    check("ASS quema el gancho en el cuadro 0", "0:00:00.00,0:00:03.60,Open" in txt and "¿QUÉ DIJO?" in txt)
    check("ASS mantiene contexto y dramómetro", "Antes de esto, pasó algo" in txt and "DRAMÓMETRO 80%" in txt)

    # --- La voz se mezcla sobre el video: sin tarjeta, con amix en el filter_complex
    work = Path(td)
    clip = work / "clip.mp4"
    clip.write_bytes(b"x")
    voice = work / "voice.mp3"
    voice.write_bytes(b"x")
    captured = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="60")

    old_run = original.subprocess.run
    try:
        original.subprocess.run = fake_run
        original.concat([clip], work / "out.mp4", work, audio_extra={0: voice})
    finally:
        original.subprocess.run = old_run
    cmd = captured["cmd"]
    check("concat mezcla voz sobre el clip", "amix=inputs=2:duration=first:normalize=0" in " ".join(cmd))
    check("concat trae la voz como entrada", str(voice.resolve()) in cmd)

print(f"OK: {ok} comprobaciones de apertura")
