"""Parte 12: página Hacerlo viral (estudio de miniaturas, aprobación, miniatura al publicar). Ejecuta: python test_parte12.py"""
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import config
import studio
import thumb

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


# ---- estilos y miniatura real con ffmpeg
check("hay 4 estilos y el de siempre es amarillo", set(thumb.STYLES) == {"amarillo", "rojo", "blanco", "centro"} and thumb.DEFAULT_STYLE == "amarillo")
check("estilo raro cae al amarillo", thumb.style_of("loquesea") is thumb.STYLES["amarillo"] and thumb.style_of(None) is thumb.STYLES["amarillo"])
tmp = Path(tempfile.mkdtemp())
vid = tmp / "v.mp4"
have_ff = shutil.which("ffmpeg") is not None
if have_ff:
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=25:duration=6", "-pix_fmt", "yuv420p", str(vid)], check=True)
    j1, t1 = thumb.make_t(vid, "Nadie lo esperaba", tmp / "a.jpg", at=2.0, style="rojo")
    j2, t2 = thumb.make_t(vid, "Nadie lo esperaba", tmp / "b.jpg", at=4.0, style="blanco")
    check("miniatura en el segundo pedido", j1 and j1.exists() and t1 == 2.0)
    check("otro segundo y otro estilo dan otra imagen", j2 and j2.read_bytes() != j1.read_bytes() and t2 == 4.0)
    j3, t3 = thumb.make_t(vid, "x", tmp / "c.jpg", at=999)
    check("segundo fuera del video se acota al final", j3 and t3 < 6)
    check("make() sigue devolviendo solo la ruta", thumb.make(vid, "Hola mundo", tmp / "d.jpg", at=1) is not None)
    check("pesa menos de 2 MB (límite de YouTube)", j1.stat().st_size < config.THUMB_MAX_BYTES)

# ---- validación de pedidos
check("pedido sin acción no vale", studio.clean_req({}) is None and studio.clean_req(None) is None and studio.clean_req("x") is None)
check("pedido con error no se repite", studio.clean_req({"action": "thumbs", "a": {"text": "x"}, "error": "falló"}) is None)
check("acción rara no vale", studio.clean_req({"action": "borrar_todo"}) is None)
check("thumbs sin ninguna miniatura no vale", studio.clean_req({"action": "thumbs"}) is None)
r = studio.clean_req({"action": "thumbs", "a": {"text": "  Se   armó   ", "time": "3.5", "style": "ROJO"}, "b": {"time": -4, "style": "hack"}})
check("texto limpio, segundo y estilo válidos", r["slots"]["a"] == {"text": "Se armó", "time": 3.5, "style": "rojo"})
check("segundo negativo y estilo raro se ignoran", r["slots"]["b"] == {"text": "", "time": None, "style": ""})
check("texto se acota a 40", len(studio.clean_req({"action": "thumbs", "a": {"text": "x" * 200}})["slots"]["a"]["text"]) == 40)
check("segundo no numérico se ignora", studio.clean_req({"action": "thumbs", "a": {"time": "abc"}})["slots"]["a"]["time"] is None)
check("reanalyze no necesita miniaturas", studio.clean_req({"action": "reanalyze"})["action"] == "reanalyze")

# ---- textos y rutas
v = {"thumb_text": "SE ARMÓ", "thumb_texts": ["SE ARMÓ", "NADIE LO VIO"]}
check("texto por defecto A y B", studio.default_text(v, "a") == "SE ARMÓ" and studio.default_text(v, "b") == "NADIE LO VIO")
check("sin IA usa el título", studio.default_text({}, "a", "Pelea total en vivo hoy mismo") == "Pelea total en vivo")
check("ruta nueva cada vez", studio.new_thumb_path("s1", "c1", "a", 100) != studio.new_thumb_path("s1", "c1", "a", 101))
check("ruta con la forma de siempre", studio.new_thumb_path("s1", "c1", "b", 5) == "thumbs/s1/c1_b_5.jpg")


# ---- base de datos simulada
class FakeDB:
    def __init__(self, clip, reqs=None, missing=None):
        self.clip, self.updates, self.uploads, self.removed = clip, [], [], []
        self.reqs, self.missing = reqs or [], missing or []

    def download_clip(self, p):
        return vid.read_bytes()

    def upload_thumb(self, p, f):
        self.uploads.append(p)

    def update_clip(self, cid, **f):
        self.updates.append((cid, f))
        self.clip.update(f)

    def remove_file(self, p):
        self.removed.append(p)

    def clips_with_requests(self, n):
        return self.reqs

    def clips_missing_thumbs(self, n):
        return self.missing


def clip(**kw):
    c = {"id": "c1", "source_id": "s1", "title": "Pelea en vivo", "storage_path": "s1/c1.mp4", "thumb_path": "thumbs/s1/c1.jpg",
         "thumb_b_path": "thumbs/s1/c1_b.jpg", "viral": {"score": 80, "thumb_text": "SE ARMÓ", "thumb_texts": ["SE ARMÓ", "NADIE"]},
         "viral_status": "review", "captions": [{"w": "nadie", "start": 0, "end": 1}, {"w": "lo", "start": 1, "end": 2}], "start_sec": 0, "end_sec": 30,
         "viral_score": 80, "hashtags": ["#a"]}
    c.update(kw)
    return c


if have_ff:
    # pedido de miniaturas: guarda rutas nuevas, borra las viejas, anota texto/estilo/segundo y limpia el pedido
    c = clip(viral_req={"action": "thumbs", "a": {"text": "ME LO CREO", "time": 3, "style": "rojo"}})
    d = FakeDB(c)
    check("handle hace el pedido", studio.handle(c, d, tmp / "w") is True)
    cid, f = d.updates[-1]
    check("viral_req queda vacío", f["viral_req"] is None)
    check("miniatura A nueva (otra ruta)", f["thumb_path"].startswith("thumbs/s1/c1_a_") and f["thumb_path"] != "thumbs/s1/c1.jpg")
    check("la B no se toca si no la pediste", "thumb_b_path" not in f)
    check("se borró la A vieja, no la B", d.removed == ["thumbs/s1/c1.jpg"])
    check("se guardó texto, estilo y segundo", f["viral"]["thumb"]["a"] == {"text": "ME LO CREO", "style": "rojo", "time": 3.0})
    check("el texto principal quedó igual al de la A", f["viral"]["thumb_text"] == "ME LO CREO")
    check("se subió 1 imagen", len(d.uploads) == 1)
    check("limpia su carpeta de trabajo", not (tmp / "w" / "c1").exists())

    # solo cambia el texto: se queda en el mismo cuadro
    c2 = clip(viral={"thumb": {"a": {"text": "VIEJO", "style": "blanco", "time": 4.0}}}, viral_req={"action": "thumbs", "a": {"text": "NUEVO"}})
    d2 = FakeDB(c2)
    studio.handle(c2, d2, tmp / "w")
    f2 = d2.updates[-1][1]
    check("solo texto: mismo segundo y mismo estilo", f2["viral"]["thumb"]["a"] == {"text": "NUEVO", "style": "blanco", "time": 4.0})

    # las dos a la vez
    c3 = clip(viral_req={"action": "thumbs", "a": {"time": 1}, "b": {"text": "OTRA", "time": 5, "style": "centro"}})
    d3 = FakeDB(c3)
    studio.handle(c3, d3, tmp / "w")
    f3 = d3.updates[-1][1]
    check("A y B a la vez", "thumb_path" in f3 and "thumb_b_path" in f3 and len(d3.uploads) == 2 and len(d3.removed) == 2)

    # tick: pedido + miniatura que faltaba
    c4 = clip(thumb_path=None, thumb_b_path=None, viral_req=None)
    d4 = FakeDB(c4, reqs=[], missing=[c4])
    config.THUMBS, config.VIRAL, config.VIRAL_THUMB_AB = True, True, True
    check("tick hace la miniatura que faltaba (A y B)", studio.tick(d4, tmp / "w") == 1 and "thumb_path" in d4.updates[-1][1] and "thumb_b_path" in d4.updates[-1][1])

# clip sin archivo -> error visible en la web, no se atasca
c5 = clip(storage_path=None, viral_req={"action": "thumbs", "a": {"text": "x"}})
d5 = FakeDB(c5)
check("sin archivo: falla con motivo", studio.handle(c5, d5, tmp / "w") is False)
check("el error queda en viral_req para la web", "archivo" in d5.updates[-1][1]["viral_req"]["error"])
check("un pedido con error ya no lo recoge el worker", studio.clean_req(c5["viral_req"]) is None)

# pedido corrupto se limpia
c6 = clip(viral_req={"action": "thumbs"})
d6 = FakeDB(c6)
check("pedido corrupto: se borra", studio.handle(c6, d6, tmp / "w") is False and d6.updates[-1][1] == {"viral_req": None})

# backfill que falla se marca para no repetirlo
c7 = clip(thumb_path=None, thumb_b_path=None, storage_path=None, viral={"score": 70})
d7 = FakeDB(c7)
check("backfill fallido se marca", studio.backfill(c7, d7, tmp / "w") is False and d7.updates[-1][1]["viral"]["thumb_tried"] is True)

# ---- re-análisis (IA simulada): no toca tu título ni tus hashtags; respeta lo aprobado
import viral  # noqa: E402
fake_llm = types.SimpleNamespace(ask=lambda *a, **k: {"titles": [{"t": "Nadie esperaba lo que pasó aquí", "angle": "curiosidad"}], "thumb_texts": ["SE ARMÓ"], "hashtags": ["#a", "#b"], "risks": []})
sys.modules["llm"] = fake_llm
c8 = clip(viral={"title_original": "Orig", "thumb": {"a": {"text": "X", "style": "rojo", "time": 2}}}, viral_status="approved", title="Mi título")
fr = studio.reanalyze(c8)
check("re-análisis no toca el título ni los hashtags de tu clip", "title" not in fr and "hashtags" not in fr)
check("sigue aprobado", "viral_status" not in fr)
check("conserva la miniatura que elegiste", fr["viral"]["thumb"]["a"]["style"] == "rojo")
check("trae sugerencias nuevas", fr["viral"]["titles"] and fr["viral"]["hashtags"])
check("si no estaba aprobado, se recalcula el estado", "viral_status" in studio.reanalyze(clip(viral_status="review")))

# ---- aprobación obligatoria (db real con Supabase simulado)
sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *a, **k: object())   # sin red ni llaves reales
import db  # noqa: E402


class Q:
    def __init__(self, data):
        self.data, self.calls = data, []

    def __getattr__(self, n):
        def f(*a, **k):
            self.calls.append((n, a))
            return self
        return f

    @property
    def not_(self):
        return self

    def execute(self):
        return types.SimpleNamespace(data=self.data)


class SB:
    def __init__(self, tables):
        self.tables, self.last = tables, {}

    def table(self, n):
        q = Q(self.tables.get(n, []))
        self.last[n] = q
        return q


db._vconf.update({"at": 0.0, "val": None})
db.sb = SB({"viral_config": [{"require_approval": True}]})
check("lee el ajuste de la web", db.require_approval() is True)
db._vconf.update({"at": 0.0, "val": None})
db.sb = SB({"viral_config": []})
config.VIRAL_REQUIRE_APPROVAL = True
check("sin fila usa el respaldo del .env", db.require_approval() is True)
db._vconf.update({"at": 0.0, "val": None})
db.sb = SB({})
config.VIRAL_REQUIRE_APPROVAL = False
check("sin ajuste ni .env: no exige aprobación", db.require_approval() is False)
db._vconf.update({"at": 0.0, "val": None})
db.sb = types.SimpleNamespace(table=lambda n: (_ for _ in ()).throw(RuntimeError("no existe la tabla")))
check("si falla la tabla no se cae", db.require_approval() is False)

db._vconf.update({"at": 0.0, "val": True})
sb = SB({"clips": [], "posts": []})
db._vconf["at"] = __import__("time").time()
db.sb = sb
db.clips_ready_for_queue(["facebook"])
used = [a for n, a in sb.last["clips"].calls if n == "in_"]
check("con aprobación obligatoria la cola solo toma aprobados", used and used[0][1] == ["approved"])
db._vconf.update({"at": __import__("time").time(), "val": False})
sb = SB({"clips": [], "posts": []})
db.sb = sb
db.clips_ready_for_queue(["facebook"])
used = [a for n, a in sb.last["clips"].calls if n == "in_"]
check("sin ella toma listos y aprobados", used and used[0][1] == ["ready", "approved"])

# filtros de pedidos y miniaturas faltantes
db.sb = SB({"clips": [{"id": "1", "viral_req": {"action": "thumbs"}}, {"id": "2", "viral_req": {"error": "x"}}, {"id": "3", "viral_req": {"action": "reanalyze", "error": "y"}},
                      {"id": "4", "viral_req": {"action": "reanalyze"}}]})
check("solo toma pedidos con acción y sin error", [r["id"] for r in db.clips_with_requests(5)] == ["1", "4"])
db.sb = SB({"clips": [{"id": "1", "viral": {}, "viral_req": None}, {"id": "2", "viral": {"thumb_tried": True}, "viral_req": None}, {"id": "3", "viral": {}, "viral_req": {"action": "thumbs"}}]})
check("no reintenta los marcados ni los que tienen pedido", [r["id"] for r in db.clips_missing_thumbs(5)] == ["1"])
db.sb = types.SimpleNamespace(table=lambda n: (_ for _ in ()).throw(RuntimeError("falta 0014")))
check("sin la migración devuelve vacío", db.clips_with_requests() == [] and db.clips_missing_thumbs() == [])

check("miniatura elegida: A por defecto", db.cover_path({"thumb_path": "a", "thumb_b_path": "b"}) == "a")
check("miniatura elegida: B si la elegiste", db.cover_path({"thumb_path": "a", "thumb_b_path": "b", "thumb_choice": "b"}) == "b")
check("elegiste B pero no existe: usa A", db.cover_path({"thumb_path": "a", "thumb_choice": "b"}) == "a")
check("sin miniatura: None", db.cover_path({}) is None and db.cover_path(None) is None)

# ---- publicadores usan la miniatura elegida
import poster  # noqa: E402
import publisher_ig  # noqa: E402
import publisher_yt  # noqa: E402


class PDB:
    def signed_url(self, p):
        return f"https://x/{p}"

    def download_clip(self, p):
        return b"JPG" if p.endswith(".jpg") else b"MP4"

    cover_path = staticmethod(db.cover_path)


got = {}
ig = types.SimpleNamespace(publish=lambda url, text, **k: got.update(ig=(url, k)) or "IG1")
poster.publish_post({"id": "p1", "network": "instagram"}, {"storage_path": "s/c.mp4", "title": "t", "thumb_path": "thumbs/s/c_a_1.jpg", "thumb_choice": "b", "thumb_b_path": "thumbs/s/c_b_1.jpg"}, PDB(), ig=ig)
check("Instagram recibe la portada elegida (B)", got["ig"][1] == {"cover_url": "https://x/thumbs/s/c_b_1.jpg"})
got.clear()
ig2 = types.SimpleNamespace(publish=lambda url, text: got.update(plain=True) or "IG2")
poster.publish_post({"id": "p2", "network": "instagram"}, {"storage_path": "s/c.mp4", "title": "t"}, PDB(), ig=ig2)
check("sin miniatura Instagram se llama como antes", got.get("plain") is True)
yt = types.SimpleNamespace(publish=lambda data, title, text, tags=None, thumb=None: got.update(yt=thumb) or "YT1")
poster.publish_post({"id": "p3", "network": "youtube"}, {"storage_path": "s/c.mp4", "title": "t", "thumb_path": "thumbs/s/c_a_1.jpg"}, PDB(), yt=yt, workdir=tmp)
check("YouTube recibe los bytes de la miniatura", got["yt"] == b"JPG")

# Instagram: si rechaza la portada, publica sin ella
calls = []


class Resp:
    def __init__(self, ok, js=None, text=""):
        self.ok, self._js, self.text = ok, js or {}, text

    def json(self):
        return self._js


def fake_post(url, data=None, **k):
    calls.append(dict(data or {}))
    if url.endswith("/media") and "cover_url" in (data or {}):
        return Resp(False, text="cover inválida")
    return Resp(True, {"id": "123"})


publisher_ig.requests = types.SimpleNamespace(post=fake_post, get=lambda *a, **k: types.SimpleNamespace(json=lambda: {"status_code": "FINISHED"}))
config.IG_TOKEN, config.IG_USER_ID = "t", "u"
check("Instagram sin portada válida publica igual", publisher_ig.publish("https://v", "hola", cover_url="https://c.jpg") == "123")
check("primero probó con portada y luego sin ella", "cover_url" in calls[0] and "cover_url" not in calls[1])
calls.clear()
publisher_ig.publish("https://v", "hola")
check("sin cover_url no manda portada", "cover_url" not in calls[0])

# YouTube: la miniatura nunca tumba la publicación
yt_calls = []


def yt_post(url, **k):
    yt_calls.append(url)
    if "thumbnails" in url:
        return types.SimpleNamespace(ok=False, text="forbidden")
    if "oauth2" in url:
        return types.SimpleNamespace(ok=True, json=lambda: {"access_token": "T"})
    return types.SimpleNamespace(ok=True, headers={"Location": "https://up"})


publisher_yt.requests = types.SimpleNamespace(post=yt_post, put=lambda *a, **k: types.SimpleNamespace(ok=True, json=lambda: {"id": "VID"}))
check("YouTube: miniatura rechazada, el video sale igual", publisher_yt.publish(b"mp4", "t", "d", [], thumb=b"JPG") == "VID" and any("thumbnails" in u for u in yt_calls))
check("miniatura de más de 2 MB ni se intenta", publisher_yt.set_thumbnail("VID", b"x" * (config.THUMB_MAX_BYTES + 1), "T") is False)
yt_calls.clear()
publisher_yt.publish(b"mp4", "t", "d", [])
check("sin miniatura no llama al endpoint de miniaturas", not any("thumbnails" in u for u in yt_calls))

shutil.rmtree(tmp, ignore_errors=True)
print(f"OK: {ok} pruebas de la Parte 12")
