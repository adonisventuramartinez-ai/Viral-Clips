"""Parte 15: gancho del inicio (hook.py). Ejecuta: python test_gancho.py"""
import hook

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


def mk(text, t0=0.0, step=0.4, gap_after=None):
    """Palabras de prueba: una por `step` s. gap_after = {índice: pausa} para simular silencios."""
    gap_after = gap_after or {}
    out, t = [], t0
    for i, w in enumerate(text.split()):
        out.append({"w": w, "start": round(t, 2), "end": round(t + step * 0.8, 2)})
        t += step + gap_after.get(i, 0.0)
    return out


# ---- frases y puntajes
w = mk("Bueno eh hola. ¿Sabes lo que me hizo ayer en vivo? Nadie lo esperaba.")
st = hook.sentence_starts(w)
check("detecta inicio de frase por punto", 0 in st and 3 in st and 11 in st)
check("pausa larga separa frases sin punto", 2 in hook.sentence_starts(mk("uno dos tres cuatro", gap_after={1: 1.0})))
check("pregunta > muletilla", hook.start_score(w, 3) > hook.start_score(w, 0))
check("'pero...' se castiga como arranque", hook.start_score(mk("Pero eso no es lo peor que pasó aquí hoy"), 0)
      < hook.start_score(mk("Lo peor de todo pasó aquí hoy mismo en vivo"), 0))

# ---- refine_start: salta saludo y entra en la frase fuerte
words = mk("Bueno eh hola a todos. ¿Sabes lo que me hizo ayer en vivo frente a todos? Se salió de control y empezó a gritar por toda la casa "
           "mientras todos mirábamos sin creerlo y entonces pasó lo más increíble que he visto en mi vida aquí en el programa de hoy "
           "y la gente no paraba de reír ni de comentar lo sucedido esa noche tan larga.")
end = words[-1]["end"] + 0.1
ns, note = hook.refine_start(words, 0.0, end)
check("entra en la pregunta, no en el saludo", ns > 1.5 and note and "movido" in note)
check("el nuevo inicio cae antes de la primera palabra fuerte", ns < words[5]["start"])
check("el nuevo inicio no pisa la palabra anterior", ns >= words[4]["end"])
check("el clip sigue durando lo mínimo", end - ns >= 12.0)

# ---- no toca un clip que ya arranca bien
good = mk("¿Sabes lo que acaba de pasar aquí en vivo? Nadie lo esperaba y todo el mundo se quedó callado mirando la escena completa "
          "mientras el invitado se levantaba de la silla muy molesto y dijo que se iba para su casa de inmediato sin despedirse de nadie.")
ns2, note2 = hook.refine_start(good, 0.0, good[-1]["end"] + 0.1)
check("si ya arranca bien no cambia", ns2 == 0.0 and note2 is None)

# ---- respeta el mínimo: un clip corto no se recorta
short = mk("Bueno eh hola. ¿Sabes lo que me hizo ayer? Se fue sin decir nada de nada.")
ns3, _ = hook.refine_start(short, 0.0, short[-1]["end"] + 0.1)
check("clip corto no se recorta por debajo del mínimo", short[-1]["end"] - ns3 >= 12.0 or ns3 == 0.0)

# ---- sin frase mejor: quita solo muletillas sueltas
mul = mk("Bueno eh la verdad es que ese día se armó una pelea tremenda en el estudio y nadie sabía qué hacer con todo aquello que estaba "
         "pasando delante de las cámaras mientras la audiencia miraba atónita sin poder creerlo todavía hoy en día.")
ns4, note4 = hook.refine_start(mul, 0.0, mul[-1]["end"] + 0.1)
check("quita muletillas del arranque", ns4 > 0.5 and note4 and "muletilla" in note4)
check("no quita palabras con significado", ns4 < mul[2]["start"] + 0.01)

# ---- poca transcripción: no hace nada
check("pocas palabras: no toca", hook.refine_start(mk("hola que tal"), 0.0, 3.0) == (0.0, None))
check("sin palabras: no toca", hook.refine_start([], 5.0, 40.0) == (5.0, None))

# ---- limpieza del gancho
check("quita comillas y emojis", hook.clean_hook("\"Mira lo que pasó\" 🔥") == "Mira lo que pasó")
check("máximo 7 palabras", len(hook.clean_hook("uno dos tres cuatro cinco seis siete ocho nueve diez").split()) <= 8)
check("máximo 44 caracteres", len(hook.clean_hook("a" * 10 + " " + "palabra " * 12)) <= 46)
check("no termina en 'de la'", not hook.clean_hook("Esto fue lo que pasó con el hijo de la vecina del frente en la casa").split()[-1].rstrip("…").lower() in hook.TAIL_STOP)
check("vacío queda vacío", hook.clean_hook("   ") == "" and hook.clean_hook(None) == "")
check("conserva ? y !", hook.clean_hook("¿Quién tiene la razón?") == "¿Quién tiene la razón?")

# ---- genéricos
check("genérico detectado", hook.is_generic("¡MIRA ESTO!") and hook.is_generic("Nadie lo esperaba") and hook.is_generic("wow"))
check("específico no es genérico", not hook.is_generic("Le dijo la verdad delante de todos"))
check("una palabra es genérica", hook.is_generic("Increíble") and hook.is_generic(""))

# ---- best_hook
cw = mk("Bueno hola. Le dijo la verdad delante de todos los invitados. Y se quedó callada.")
ce = cw[-1]["end"] + 0.1
check("usa el gancho de la IA si dice algo", hook.best_hook("Le dijo la verdad en su cara", "T", cw, 0.0, ce) == "Le dijo la verdad en su cara")
d = hook.best_hook("¡MIRA ESTO!", "Título largo del clip que no cabe", cw, 0.0, ce)
check("gancho genérico se cambia por uno del clip", "verdad" in d.lower() and d.lower() != "mira esto")
check("si no hay transcripción usa el título", hook.best_hook("", "La pelea del año", [], 0.0, 30.0) == "La pelea del año")
check("último recurso nunca queda vacío", hook.best_hook("", "", [], 0.0, 30.0) == "MIRA ESTO")
risky = mk("Ese estafador me robó todo mi dinero ayer mismo. Después lo vimos salir corriendo por la puerta.")
check("no usa una frase con insultos como gancho", "estafador" not in hook.best_hook("wow", "", risky, 0.0, risky[-1]["end"] + 0.1).lower())
check("gancho de la IA con insulto se descarta", "estafador" not in hook.best_hook("Ese estafador lo hizo otra vez", "Otro título", [], 0.0, 30.0).lower())

print(f"OK: {ok} comprobaciones del gancho")
