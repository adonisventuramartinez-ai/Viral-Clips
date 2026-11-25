"""Audio del directo: el texto sigue a la voz desde el primer segundo."""
import config
import render

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


START, END = 10.0, 15.0
PALABRAS = [
    {"w": "antes", "start": 9.8, "end": 10.2},   # venía de antes del corte (SMART_START)
    {"w": "hola", "start": 10.4, "end": 11.0},
    {"w": "borde", "start": 14.8, "end": 15.4},  # se pasa del final
    {"w": "luego", "start": 15.2, "end": 15.8},  # fuera del clip
]

# --- La palabra que empezó antes del corte no se pierde y el desfase se aplica una vez
synced = render.sync_words_for_clip(PALABRAS, START, END)
check("palabra previa incluida", [w["w"] for w in synced] == ["antes", "hola", "borde"])
check("tiempo negativo acotado a 0", synced[0]["start"] == 0.0)
check("desfase aplicado", abs(synced[1]["start"] - 0.05) < 1e-6)
check("final acotado al clip", synced[-1]["end"] == 5.0)
check("tiempos dentro del clip", all(0 <= w["start"] < w["end"] <= 5.0 for w in synced))

# --- Sin desfase tampoco salen tiempos negativos ni se cuela la palabra de después
synced0 = render.sync_words_for_clip(PALABRAS, START, END, sync=0)
check("sin desfase incluye la palabra previa", synced0[0]["w"] == "antes")
check("sin desfase acota el inicio", synced0[0]["start"] == 0.0)
check("palabra posterior excluida", all(w["w"] != "luego" for w in synced0))

# --- El ASS quemado no tiene tiempos negativos y el gancho sigue en el cuadro 0
texto = render.build_ass(PALABRAS, START, END, layout="crop", hook="¿Y eso qué fue?")
dialogos = [x for x in texto.splitlines() if x.startswith("Dialogue:")]
check("hay subtítulo y gancho", len(dialogos) >= 2)
check("gancho en 0", dialogos[0].split(",")[1] == "0:00:00.00")
check("sin tiempos negativos", "0:-" not in texto)
check("subtítulo de la palabra previa presente", "ANTES" in texto)

check("desfase por defecto del directo", config.SUB_SYNC_OFFSET == -0.35)
print(f"AUDIO LIVE OK · {ok} comprobaciones")
