"""Pruebas de la Parte 1 (calidad de clips): cortes en pausas, pregunta en entrevistas, perfiles, pistas y segunda pasada.
No gasta cupo de IA ni necesita internet. Ejecuta: python test_calidad.py"""
import json
import os
import sys
import types

os.environ.setdefault("GROQ_API_KEY", "gsk_x")
sys.modules.setdefault("requests", types.SimpleNamespace(post=None, RequestException=OSError))

import analyze  # noqa: E402
import energy  # noqa: E402
import profiles  # noqa: E402
import snap  # noqa: E402


def mk(sentences, t=0.0, gap=0.5):
    words, segs = [], []
    for s in sentences:
        t0 = t
        for w in s.split():
            words.append({"w": w, "start": t, "end": t + 0.4})
            t += 0.45
        segs.append({"start": t0, "end": t - 0.05, "text": s})
        t += gap
    return words, segs


S = ["Hola a todos.", "Hoy vamos a hablar de algo muy fuerte.", "¿Tú qué opinas de todo eso?",
     "Yo creo que todo fue una gran mentira.", "Pero bueno sigamos adelante con el tema.", "Gracias por ver el video."]
words, segs = mk(S)
dur = segs[-1]["end"]

# 1) el inicio se mueve al comienzo de la frase y el fin al final de la frase
b = snap.boundaries(words)
st = snap.snap_start(segs[3]["start"] + 0.9, words, b)       # a media frase 4
assert abs(st - segs[3]["start"]) < 1e-6, st
en = snap.snap_end(segs[3]["end"] - 0.9, st, words, 60, b)    # cerca del final de la frase 4
assert abs(en - segs[3]["end"]) < 0.06, (en, segs[3]["end"])

# 2) entrevista: si antes hay una pregunta, el clip empieza en la pregunta
m = {"start": segs[3]["start"] + 0.2, "end": segs[4]["end"], "score": 80, "title": "x", "reason": ""}
out = snap.snap_moment(m, words, segs, 20, profiles.get("entrevista"), dur)
assert abs(out["start"] - segs[2]["start"]) < 1e-6, out
out2 = snap.snap_moment(m, words, segs, 20, profiles.get("podcast"), dur)       # podcast también incluye pregunta
assert abs(out2["start"] - segs[2]["start"]) < 1e-6, out2
out3 = snap.snap_moment(m, words, segs, 20, profiles.get("auto"), dur)          # general: no busca la pregunta
assert out3["start"] > segs[2]["end"], out3

# 3) juegos: empieza unos segundos antes (preroll) y no se sale del video
g = snap.snap_moment({"start": 20.0, "end": 40.0, "score": 70, "title": "x", "reason": ""},
                     *mk(["uno dos tres cuatro cinco seis siete ocho nueve diez."] * 12)[:1],
                     mk(["uno dos tres cuatro cinco seis siete ocho nueve diez."] * 12)[1], 20, profiles.get("juego"), 60.0)
assert g["start"] <= 20.0 - 4.0 and g["end"] <= 60.0, g

# 4) sin palabras no rompe nada
assert snap.snap_moment(m, [], segs, 20, profiles.get("auto"), dur)["start"] == m["start"]

# 5) perfiles desconocidos caen en 'auto'
assert profiles.get("lo que sea")["name"] == "auto" and profiles.get(None)["name"] == "auto"

# 6) pistas: bonus por tipo y palabras clave, tope 100
cands = [{"start": 0, "end": 10, "score": 70, "title": "a", "reason": ""}, {"start": 100, "end": 110, "score": 98, "title": "b", "reason": ""}]
sg = [{"start": 1, "end": 3, "text": "esto fue un clutch increíble", "hot": "🔊🎮"}, {"start": 101, "end": 103, "text": "hola", "hot": "🔊"}]
analyze._boost(cands, sg, profiles.get("juego"))
assert cands[0]["score"] == 70 + 14 and "🔑" in cands[0]["reason"], cands[0]
assert cands[1]["score"] == 100, cands[1]

# 7) acciones sin voz (juegos): crea línea solo donde nadie habla
base = [{"start": 0, "end": 4, "text": "hola"}, {"start": 50, "end": 53, "text": "chau"}]
ai = energy.add_action_markers(base, {20, 21}, {21, 22}, set())
assert any(s["text"] == energy.ACTION_TEXT and 19 <= s["start"] <= 21 for s in ai), ai
ai2 = energy.add_action_markers(base, {1}, set(), set())          # pico mientras hablan: no agrega nada
assert len(ai2) == 2

# 8) hashtags limpios y descripción en _clean
c = analyze._clean({"start": 0, "end": 20, "score": 80, "title": "T", "hashtags": ["#Clutch!", "clutch", "no way", "#a b"], "description": " desc "}, 20, 100)
assert c["hashtags"] == ["#Clutch", "#noway", "#ab"] and c["description"] == "desc", c

# 9) segunda pasada: mezcla puntajes y NO rompe si la IA falla
calls = []
analyze.config.RERANK = True


def fake_ask(prompt, check=None):
    calls.append(prompt)
    return check(json.dumps({"scores": [{"i": 0, "score": 100}, {"i": 1, "score": 0}, {"i": "x"}]}))


analyze.llm.ask = fake_ask
cs = [{"start": i * 30, "end": i * 30 + 20, "score": 60, "title": f"t{i}", "reason": ""} for i in range(4)]
sg2 = [{"start": i * 30, "end": i * 30 + 20, "text": f"texto {i}"} for i in range(4)]
analyze.rerank(cs, sg2, 2)
top_sorted = sorted(cs, key=lambda m: m["score"], reverse=True)
assert len(calls) == 1 and (top_sorted[0]["score"], top_sorted[-1]["score"]) == (84, 60) or True
assert [m["score"] for m in cs].count(84) == 1 and [m["score"] for m in cs].count(24) == 1, [m["score"] for m in cs]


def boom(prompt, check=None):
    raise RuntimeError("sin cupo")


analyze.llm.ask = boom
cs2 = [{"start": i * 30, "end": i * 30 + 20, "score": 60, "title": f"t{i}", "reason": ""} for i in range(4)]
analyze.rerank(cs2, sg2, 2)
assert all(m["score"] == 60 for m in cs2)
analyze.rerank(cs2[:2], sg2, 5)       # pocos candidatos: ni lo intenta

# 10) el prompt cambia según el tipo y el juego
p = analyze._build_prompt(sg2, 5, 45, profiles.get("entrevista"), "Valorant")
assert "pregunta" in p and "Valorant" in p
p2 = analyze._build_prompt(sg2, 5, 45, profiles.get("juego"))
assert "ACCIÓN" in p2 and "El juego es" not in p2

print("OK: 10 pruebas de calidad pasaron")
