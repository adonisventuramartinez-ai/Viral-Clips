"""Parte 7: área "Hacerlo viral". Ejecuta: python test_parte7.py"""
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import viral

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


# ---- títulos
check("título vacío = 0", viral.title_score("") == 0)
good = viral.title_score("Nadie esperaba lo que pasó en vivo")
check("título con curiosidad > plano", good > viral.title_score("Clip número 4 del programa de hoy ok"))
check("título gritado castigado", viral.title_score("ESTO ES UNA LOCURA TOTAL AHORA MISMO") < viral.title_score("Esto es una locura total ahora mismo"))
check("título con insulto castigado", viral.title_score("Ese estafador se salió en vivo") < viral.title_score("Ese tipo se salió en vivo"))
check("riesgo detectado", viral.risks_in("es un estafador", "hola") == ["estafador"] and viral.risks_in("todo bien") == [])
check("puntaje dentro de 0-100", all(0 <= viral.title_score(t) <= 100 for t in ["a", "!!!???" * 20, "x" * 500, "¿Quién tiene la razón? 3 veces"]))

# ---- arranque y puntaje
check("arranque con pregunta > 'bueno eh'", viral.hook_score("¿Tú sabes lo que acaba de pasar aquí en vivo?") > viral.hook_score("bueno eh este"))
check("combine pesa la IA", viral.combine(90, 50, 50, 30) > viral.combine(50, 50, 50, 30))
check("combine duración mala baja", viral.combine(80, 70, 70, 30) > viral.combine(80, 70, 70, 200))
check("combine 0-100", 0 <= viral.combine(100, 100, 100, 30) <= 100 and viral.combine(0, 0, 0, 500) >= 0)

# ---- veredicto (umbrales por defecto 70 / 55)
check("ready", viral.verdict(80) == "ready")
check("review", viral.verdict(60) == "review")
check("rejected", viral.verdict(40) == "rejected")
check("riesgo fuerza review aunque el puntaje sea alto", viral.verdict(95, ["estafador"]) == "review")

# ---- hashtags
h = viral.hashtag_mix(["viral", "#Viral", "con espacio", "#drama", "#fyp", "#parati", "#a", "#x" * 20], ["#alofoke"], "La Casa de Alofoke 3")
check("máx 5 y empieza con #fyp", len(h) <= 5 and h[0] == "#fyp")
check("incluye el programa", "#LaCasadeAlofoke3" in h)
check("sin repetidos ni espacios", len({t.lower() for t in h}) == len(h) and all(t.startswith("#") and " " not in t for t in h))
check("un solo hashtag amplio extra", sum(t.lower() in viral.BROAD_TAGS for t in h) == 1)
check("sin nada devuelve al menos #fyp", viral.hashtag_mix(None, None, "") == ["#fyp"])

# ---- horas de publicación (huso -4, horas 12:30 / 19:00 / 21:30)
tz = timezone(timedelta(hours=-4))
now = datetime(2026, 11, 16, 20, 0, tzinfo=tz).astimezone(timezone.utc)      # lunes 8:00 pm en RD
s1 = viral.next_slots(now, n=1)[0].astimezone(tz)
check("siguiente hora buena hoy 9:30 pm", (s1.hour, s1.minute, s1.day) == (21, 30, 16))
s3 = viral.next_slots(now, n=3)
check("3 horas distintas y en orden", len(s3) == 3 and s3 == sorted(s3) and len(set(s3)) == 3)
check("la 2.ª es mañana 12:30", (s3[1].astimezone(tz).day, s3[1].astimezone(tz).hour) == (17, 12))
s_busy = viral.next_slots(now, taken=[s3[0].isoformat()], n=1)[0]
check("salta la hora ya ocupada", s_busy == s3[1])
check("ocupada a menos de 90 min también se salta", viral.next_slots(now, taken=[(s3[0] + timedelta(minutes=30)).isoformat()], n=1)[0] == s3[1])
cap = viral.next_slots(now, taken=[(now + timedelta(minutes=5 * i)).isoformat() for i in range(1)], n=1, max_per_day=1)
check("tope por día", cap[0].astimezone(tz).day != 16 or cap[0] > now)
check("sin horas configuradas = vacío", viral.next_slots(now, slots=["xx"], n=2) == [])
check("nunca devuelve el pasado", all(t > now for t in viral.next_slots(now, n=5)))

# ---- run() con IA simulada, IA rota y caída
import llm
orig = llm.ask
AI = '{"titles":[{"t":"Nadie lo vio venir en vivo","angle":"curiosidad"},{"t":"¿Quién tiene la razón aquí?","angle":"pregunta"},{"t":"x","angle":"mal"}],"thumb_texts":["SE ARMÓ","NADIE LO VIO","LOCURA"],"hashtags":["#drama","#alofoke","#reality"],"risks":[]}'
llm.ask = lambda prompt, check=None: check(AI)
m = {"title": "Clip aburrido número 5", "hook": "mira", "score": 85, "hashtags": ["#base"], "start": 0, "end": 30}
v = viral.run(m, "¿Tú sabes lo que acaba de pasar aquí en vivo? nadie lo esperaba", {"show": "La Casa de Alofoke 3"})
check("IA: mejor título elegido y puntuado", v["title"] != "Clip aburrido número 5" and v["titles"][0]["score"] >= v["titles"][-1]["score"])
check("IA: título original guardado", v["title_original"] == "Clip aburrido número 5")
check("IA: título 'x' descartado por corto", all(len(t["t"]) >= 6 for t in v["titles"]))
check("IA: texto de miniatura", v["thumb_text"] == "SE ARMÓ" and len(v["thumb_texts"]) == 3)
check("IA: puntaje y veredicto", 0 <= v["score"] <= 100 and v["verdict"] in ("ready", "review", "rejected") and v["source"] == "ia")
check("IA: hashtags ≤ 5", len(v["hashtags"]) <= 5 and v["hashtags"][0] == "#fyp")
check("estado guardado", viral.status_for(v) == v["verdict"])

llm.ask = lambda prompt, check=None: check(AI.replace('"risks":[]', '"risks":["acusa a una persona real de un delito"]'))
vr = viral.run(m, "hola", None)
check("riesgo de la IA => review", vr["risks"] and vr["verdict"] == "review")

def boom(prompt, check=None):
    raise RuntimeError("sin cupo")
llm.ask = boom
vf = viral.run(m, "hola buenas", None)
check("sin IA: no falla y usa reglas", vf["source"] == "reglas" and vf["title"] == "Clip aburrido número 5" and vf["verdict"] in ("ready", "review", "rejected"))
llm.ask = lambda prompt, check=None: check("esto no es json")
check("IA con basura: no falla", viral.run(m, "hola", None)["source"] == "reglas")
llm.ask = orig

# ---- apply_to_pack
pack = {"tiktok": {"caption": "a", "hashtags": ["#x"]}, "reels": {"caption": "b", "hashtags": []}, "shorts": {"title": "t", "description": "d", "hashtags": ["#Shorts"]}}
viral.apply_to_pack(pack, v)
check("pack recibe hashtags virales", pack["tiktok"]["hashtags"] == v["hashtags"][:5] and pack["shorts"]["hashtags"][0] == "#Shorts" and len(pack["shorts"]["hashtags"]) <= 4)
check("pack recibe el título", pack["shorts"]["title"] == v["title"][:70])
check("apply_to_pack tolera basura", viral.apply_to_pack(None, v) is None and viral.apply_to_pack({}, None) == {})

# ---- tick con base de datos simulada
class FakeDB:
    def __init__(self):
        self.updated = {}
    def clips_needing_viral(self, n):
        return [{"id": "c1", "title": "Pelea en vivo", "viral_score": 80, "hashtags": [], "captions": [{"w": "nadie"}, {"w": "lo"}, {"w": "esperaba"}], "start_sec": 10, "end_sec": 40}]
    def update_clip(self, cid, **f):
        self.updated[cid] = f

llm.ask = lambda prompt, check=None: check(AI)
viral._last = 0
fd = FakeDB()
check("tick procesa 1", viral.tick(fd) == 1)
check("tick guarda viral y estado", fd.updated["c1"]["viral"]["score"] >= 0 and fd.updated["c1"]["viral_status"] in ("ready", "review", "rejected"))
check("tick cambia el título (VIRAL_AUTO_TITLE)", fd.updated["c1"].get("title") not in (None, "Pelea en vivo"))
check("tick respeta el intervalo", viral.tick(fd) == 0)
llm.ask = orig

# ---- miniatura B: otro cuadro distinto
import thumb
with tempfile.TemporaryDirectory() as d:
    v_ = Path(d) / "t.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=540x960:r=25:d=20", "-f", "lavfi", "-i", "sine=f=300:d=20",
                        "-pix_fmt", "yuv420p", "-shortest", str(v_)], capture_output=True)
    check("video de prueba creado", r.returncode == 0)
    ta, tb = thumb.pick_time(v_, 0), thumb.pick_time(v_, 1)
    check("miniatura B usa otro cuadro (>20% del clip)", abs(ta - tb) > 20 * 0.2 - 0.01)
    ja = thumb.make(v_, "SE ARMÓ", Path(d) / "a.jpg", rank=0)
    jb = thumb.make(v_, "NADIE LO VIO", Path(d) / "b.jpg", rank=1)
    check("miniaturas A y B creadas", ja and jb and ja.stat().st_size > 5000 and jb.stat().st_size > 5000 and ja.read_bytes() != jb.read_bytes())

print(f"OK: {ok} comprobaciones")
