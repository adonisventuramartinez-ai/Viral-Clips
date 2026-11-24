"""Parte 8: cola de publicación (Facebook, Instagram, YouTube). Ejecuta: python test_parte8.py"""
import types
from datetime import datetime, timedelta, timezone

import autoqueue
import config
import poster
import publisher_ig
import publisher_yt

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


tz = timezone(timedelta(hours=-4))
now = datetime(2026, 11, 16, 20, 0, tzinfo=tz).astimezone(timezone.utc)
iso = lambda d: d.isoformat()  # noqa: E731

# ---- plan: los mejores primero, sin chocar, con topes
clips = [{"id": "a", "viral": {"score": 72}}, {"id": "b", "viral": {"score": 95}}, {"id": "c", "viral": {"score": 80}}]
p = autoqueue.plan(clips, {}, ["facebook"], now=now)
order = [x["clip_id"] for x in sorted(p, key=lambda x: x["scheduled_at"])]
check("el de más puntaje toma la hora más cercana", order == ["b", "c", "a"])
check("un post por clip y red", len(p) == 3 and len({(x["clip_id"], x["network"]) for x in p}) == 3)
two = autoqueue.plan(clips[:1], {}, ["facebook", "instagram", "youtube"], now=now)
check("un post por red", {x["network"] for x in two} == {"facebook", "instagram", "youtube"})
busy = autoqueue.plan(clips[:1], {"facebook": [p[1]["scheduled_at"]]}, ["facebook"], now=now)
check("no choca con lo ya ocupado en esa red", busy[0]["scheduled_at"] != p[1]["scheduled_at"])
check("tope de pendientes por red", len(autoqueue.plan(clips, {}, ["facebook"], now=now, pending={"facebook": 11}, max_pending=12)) == 1)
check("no programa más lejos de N días", len(autoqueue.plan(clips, {}, ["facebook"], now=now, max_ahead_days=0)) == 0)
far = autoqueue.plan([{"id": str(i), "viral": {"score": 80}} for i in range(40)], {}, ["facebook"], now=now, max_pending=99)
check("tope por día respetado (6)", all(sum(1 for y in far if datetime.fromisoformat(y["scheduled_at"]).astimezone(tz).date() == d) <= 6
                                         for d in {datetime.fromisoformat(x["scheduled_at"]).astimezone(tz).date() for x in far}))
check("sin redes = nada", autoqueue.plan(clips, {}, [], now=now) == [])
check("clip sin viral usa viral_score", autoqueue.plan([{"id": "z", "viral_score": 50}], {}, ["facebook"], now=now)[0]["clip_id"] == "z")

# ---- redes disponibles según credenciales
for k in ("FB_PAGE_ID", "FB_PAGE_TOKEN", "IG_USER_ID", "IG_TOKEN", "YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
    setattr(config, k, "")
config.AUTO_NETWORKS = []
check("sin credenciales no hay redes", autoqueue.networks_available() == [])
config.FB_PAGE_ID, config.FB_PAGE_TOKEN = "1", "t"
config.IG_USER_ID, config.IG_TOKEN = "9", "t"
check("facebook + instagram", autoqueue.networks_available() == ["facebook", "instagram"])
config.YT_CLIENT_ID, config.YT_CLIENT_SECRET, config.YT_REFRESH_TOKEN = "i", "s", "r"
check("las tres", autoqueue.networks_available() == ["facebook", "instagram", "youtube"])
config.AUTO_NETWORKS = ["youtube"]
check("AUTO_NETWORKS filtra", autoqueue.networks_available() == ["youtube"])
config.AUTO_NETWORKS = []

# ---- textos por red
clip = {"id": "c1", "title": "Pelea en vivo", "storage_path": "s/c1.mp4", "hashtags": ["#a"],
        "pack": {"reels": {"caption": "Mira esto\n¿Qué piensas?", "hashtags": ["#fyp", "#r"]},
                 "shorts": {"title": "Se armó", "description": "Resumen corto", "hashtags": ["#Shorts", "#s"]}}}
check("caption reels", "Mira esto" in poster.caption(clip, "instagram")[1] and "#r" in poster.caption(clip, "facebook")[1])
check("caption youtube usa título de shorts", poster.caption(clip, "youtube")[0] == "Se armó" and "Resumen corto" in poster.caption(clip, "youtube")[1])


# ---- base simulada
class FakeDB:
    def __init__(self, posts, clips):
        self.posts = {p["id"]: p for p in posts}
        self.clips = clips
        self.log = []

    def due_posts(self, n=5):
        return [p for p in self.posts.values() if p["status"] == "queued" and p["scheduled_at"] <= iso(datetime.now(timezone.utc))][:n]

    def claim_post(self, pid):
        if self.posts[pid]["status"] != "queued":
            return False
        self.posts[pid]["status"] = "publishing"
        self.log.append(("claim", pid))
        return True

    def update_post(self, pid, **f):
        self.posts[pid].update(f)
        self.log.append(("update", pid, f.get("status")))

    def get_clip(self, cid):
        return self.clips.get(cid)

    def download_clip(self, path):
        return b"video-bytes"

    def signed_url(self, path, s=3600):
        return "https://x.supabase.co/signed/" + path


class Rec:
    def __init__(self, ret="X1", fail=None):
        self.calls, self.ret, self.fail = [], ret, fail

    def publish_reel(self, f, text):
        self.calls.append(("fb", text))
        return None if self.fail else self.ret

    def publish(self, *a):
        self.calls.append(a)
        if self.fail:
            raise RuntimeError(self.fail)
        return self.ret


past = iso(datetime.now(timezone.utc) - timedelta(minutes=1))
future = iso(datetime.now(timezone.utc) + timedelta(hours=2))
posts = [{"id": "p1", "clip_id": "c1", "network": "facebook", "status": "queued", "scheduled_at": past},
         {"id": "p2", "clip_id": "c1", "network": "instagram", "status": "queued", "scheduled_at": past},
         {"id": "p3", "clip_id": "c1", "network": "youtube", "status": "queued", "scheduled_at": past},
         {"id": "p4", "clip_id": "c1", "network": "facebook", "status": "queued", "scheduled_at": future},
         {"id": "p5", "clip_id": "gone", "network": "facebook", "status": "queued", "scheduled_at": past}]
db = FakeDB(posts, {"c1": clip})
fb, ig, yt = Rec("FBVID"), Rec("IGID"), Rec("YTID")
n = poster.tick(db, fb=fb, ig=ig, yt=yt)
P = db.posts
check("publicó 3 (los vencidos con clip)", n == 3)
check("estados correctos", P["p1"]["status"] == P["p2"]["status"] == P["p3"]["status"] == "published")
check("ids externos guardados", (P["p1"]["external_id"], P["p2"]["external_id"], P["p3"]["external_id"]) == ("FBVID", "IGID", "YTID"))
check("el futuro NO se publica", P["p4"]["status"] == "queued")
check("clip borrado => error claro", P["p5"]["status"] == "error" and "ya no existe" in P["p5"]["error"])
check("instagram recibió URL firmada", ig.calls[0][0].startswith("https://x.supabase.co/signed/"))
check("youtube recibió bytes, título y tags", yt.calls[0][0] == b"video-bytes" and yt.calls[0][1] == "Se armó" and "#s" in yt.calls[0][3])
check("se reservó ANTES de publicar", db.log.index(("claim", "p1")) < db.log.index(("update", "p1", "published")))
n2 = poster.tick(db, fb=fb, ig=ig, yt=yt)
check("segunda vuelta no repite nada", n2 == 0 and len(fb.calls) == 1 and len(ig.calls) == 1)

# ---- errores: no se reintentan solos, nunca tumban
db2 = FakeDB([{"id": "q1", "clip_id": "c1", "network": "instagram", "status": "queued", "scheduled_at": past},
              {"id": "q2", "clip_id": "c1", "network": "facebook", "status": "queued", "scheduled_at": past}], {"c1": clip})
poster.tick(db2, fb=Rec(fail=True), ig=Rec(fail="Instagram rechazó el video"), yt=Rec())
check("error guardado con motivo", db2.posts["q1"]["status"] == "error" and "rechazó" in db2.posts["q1"]["error"])
check("facebook sin id => error", db2.posts["q2"]["status"] == "error")
check("el error no se reintenta solo", poster.tick(db2, fb=Rec(), ig=Rec(), yt=Rec()) == 0)
noclip = FakeDB([{"id": "r1", "clip_id": "c2", "network": "facebook", "status": "queued", "scheduled_at": past}], {"c2": {"id": "c2", "title": "x"}})
poster.tick(noclip, fb=Rec(), ig=Rec(), yt=Rec())
check("clip sin archivo => error claro", "no tiene archivo" in noclip.posts["r1"]["error"])

# ---- Instagram: crear contenedor, esperar, publicar (requests simulado)
calls = []


class Resp:
    def __init__(self, data, ok=True, headers=None):
        self.data, self.ok, self.headers, self.text = data, ok, headers or {}, str(data)

    def json(self):
        return self.data


seq = iter([{"status_code": "IN_PROGRESS"}, {"status_code": "FINISHED"}])


def ig_post(url, data=None, **k):
    calls.append(("POST", url, data))
    return Resp({"id": "CONT"} if url.endswith("/media") else {"id": "MEDIA9"})


def ig_get(url, params=None, **k):
    calls.append(("GET", url))
    return Resp(next(seq))


publisher_ig.requests = types.SimpleNamespace(post=ig_post, get=ig_get)
publisher_ig.time = types.SimpleNamespace(sleep=lambda s: None, time=__import__("time").time)
check("instagram devuelve el id publicado", publisher_ig.publish("https://u/v.mp4", "hola #fyp") == "MEDIA9")
check("instagram: contenedor REELS con la URL", calls[0][2]["media_type"] == "REELS" and calls[0][2]["video_url"] == "https://u/v.mp4")
check("instagram esperó al procesamiento (2 consultas)", sum(1 for c in calls if c[0] == "GET") == 2)
seq = iter([{"status_code": "ERROR", "status": "formato"}])
try:
    publisher_ig.publish("u", "c")
    check("instagram error de procesamiento", False)
except RuntimeError as e:
    check("instagram error de procesamiento", "no pudo procesar" in str(e))

# ---- YouTube: token, inicio resumable, subida
yc = []


def yt_post(url, data=None, params=None, headers=None, json=None, **k):
    yc.append(("POST", url, params, json))
    if "oauth2" in url:
        return Resp({"access_token": "AT"})
    return Resp({}, headers={"Location": "https://upload/abc"})


def yt_put(url, data=None, headers=None, **k):
    yc.append(("PUT", url, len(data)))
    return Resp({"id": "YT777"})


publisher_yt.requests = types.SimpleNamespace(post=yt_post, put=yt_put)
check("youtube devuelve el id", publisher_yt.publish(b"x" * 10, "T" * 150, "desc", ["#a", "#b"]) == "YT777")
meta = yc[1][3]
check("youtube: título ≤100, tags sin #, no es para niños", len(meta["snippet"]["title"]) == 100 and meta["snippet"]["tags"] == ["a", "b"]
      and meta["status"]["selfDeclaredMadeForKids"] is False)
check("youtube: subió los bytes a la URL de subida", yc[2][:2] == ("PUT", "https://upload/abc") and yc[2][2] == 10)

# ---- tick de autoqueue con base simulada (y apagado por defecto)
class QDB:
    created = None

    def clips_ready_for_queue(self, nets, n):
        return clips

    def posts_taken(self, nets):
        return {}

    def posts_pending(self, nets):
        return {}

    def create_posts(self, rows):
        QDB.created = rows


config.AUTO_QUEUE = False
autoqueue._last = 0
check("cola apagada: no hace nada", autoqueue.tick(QDB()) == 0 and QDB.created is None)
config.AUTO_QUEUE = True
autoqueue._last = 0
check("cola encendida: crea posts", autoqueue.tick(QDB()) == 9 and len(QDB.created) == 9)  # 3 clips x 3 redes

print(f"OK: {ok} comprobaciones")
