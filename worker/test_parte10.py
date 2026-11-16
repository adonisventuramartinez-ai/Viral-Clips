"""Parte 10: Mi página (estadísticas + mejores horas aprendidas) y Facebook como fuente. Ejecuta: python test_parte10.py"""
import types
from datetime import datetime, timedelta, timezone

import autoqueue
import config
import discover
import insights

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


tz = timezone(timedelta(hours=-4))
now = datetime(2026, 11, 16, 20, 0, tzinfo=tz).astimezone(timezone.utc)
at = lambda days_ago, h, m=30: datetime(2026, 11, 16, h, m, tzinfo=tz).astimezone(timezone.utc) - timedelta(days=days_ago)  # noqa: E731
DEF = ["12:30", "19:00", "21:30"]


def post(net, days_ago, h, views, m=30, **k):
    return {"network": net, "published_at": at(days_ago, h, m).isoformat(), "views": views, "likes": 0, "comments": 0, "shares": 0, **k}


# ---- score
check("score pesa comentarios y compartidos más que vistas", insights.score({"views": 100, "likes": 10, "comments": 5, "shares": 2}) == 100 + 30 + 40 + 20)
check("score tolera vacíos", insights.score({}) == 0 and insights.score({"views": None}) == 0)

# ---- learn: pocos datos = no cambia nada
few = [post("facebook", d, 19, 1000) for d in range(1, 6)]
r = insights.learn(few, now, tz, defaults=DEF)
check("con pocos datos no aprende y conserva tus horas", not r["all"]["enough"] and r["all"]["slots"] == DEF and r["all"]["have"] == 5)

# ---- lo reciente (menos de 24 h) no cuenta
fresh = [post("facebook", 0, 19, 99999, m=0) for _ in range(20)]
check("lo publicado hace menos de 24 h no cuenta", insights.learn(fresh, now, tz, defaults=DEF)["all"]["have"] == 0)

# ---- aprende: 19:30 y 15:30 rinden mucho, 12:30 normal, 21:30 flojo
data = []
for d in range(1, 9):
    data += [post("facebook", d, 19, 5000), post("facebook", d, 15, 4000), post("facebook", d, 12, 1500), post("facebook", d, 21, 300)]
r = insights.learn(data, now, tz, explore=False, defaults=DEF)["all"]
check("con datos suficientes aprende", r["enough"] and r["have"] == 31)   # la de 21:30 de ayer aún no cumple 24 h
check("elige las mejores horas, separadas entre sí", r["slots"] == ["12:30", "15:30", "19:30"] or r["slots"] == ["15:30", "19:30", "21:30"] or len(r["slots"]) == 3)
check("las dos mejores están (19 y 15)", {"19:30", "15:30"} <= set(r["slots"]))
check("la peor hora (21:30) no entra si hay mejores", "21:30" not in r["slots"])
best = max(r["rows"], key=lambda x: x["score"])
check("la hora de 19 es la de mayor puntaje", best["slot"] == "19:30" and best["score"] > 1)
check("las filas dicen cuántas publicaciones hay y cuáles se eligieron", all("posts" in x and "chosen" in x for x in r["rows"]) and sum(x["chosen"] for x in r["rows"]) == 3)

# ---- separación mínima: 19 y 20 no pueden elegirse juntas
close = []
for d in range(1, 9):
    close += [post("facebook", d, 19, 5000), post("facebook", d, 20, 4900), post("facebook", d, 12, 1500)]
r = insights.learn(close, now, tz, explore=False, n=2, gap_h=3, defaults=DEF)["all"]
hours = sorted(int(s[:2]) for s in r["slots"])
check("respeta la separación entre horas elegidas", len(hours) == 2 and abs(hours[0] - hours[1]) >= 3)

# ---- una hora con 1 sola publicación no gana aunque haya sido enorme
lucky = [post("facebook", d, 19, 2000) for d in range(1, 13)] + [post("facebook", 3, 10, 90000)]
r = insights.learn(lucky, now, tz, explore=False, n=1, defaults=DEF)["all"]
check("un golpe de suerte (1 publicación) no gana", r["enough"] and r["slots"] == ["19:30"])

# ---- hora de prueba (explorar)
r = insights.learn(data, now, tz, explore=True, defaults=DEF)["all"]
ex = [x for x in r["rows"] if x["explore"]]
check("incluye 1 hora de prueba", len(ex) == 1 and ex[0]["chosen"] and len(r["slots"]) == 3)
check("la hora de prueba es de día y poco probada", 10 <= int(ex[0]["slot"][:2]) <= 22 and ex[0]["posts"] == 0)
check("las 2 mejores siguen estando", {"19:30", "15:30"} <= set(r["slots"]))

# ---- mezcla de redes: YouTube con números enormes no manda sobre Facebook
mix = []
for d in range(1, 9):
    mix += [post("facebook", d, 19, 2000), post("facebook", d, 12, 500),
            post("youtube", d, 12, 900000), post("youtube", d, 19, 300000)]
a = insights.learn(mix, now, tz, explore=False, n=1, defaults=DEF)
check("cada red se compara con su propio promedio (en 'all')", a["all"]["enough"] and len(a["all"]["slots"]) == 1)
check("Facebook prefiere 19:30 y YouTube prefiere 12:30 por separado", a["facebook"]["slots"][0] == "19:30" and a["youtube"]["slots"][0] == "12:30")
check("solo salen las redes con datos", set(a) == {"all", "facebook", "youtube"})

# ---- nadie vio nada: no inventa
zero = [post("facebook", d, 19, 0) for d in range(1, 20)]
check("con 0 vistas no aprende", not insights.learn(zero, now, tz, defaults=DEF)["all"]["enough"])

# ---- completa con tus horas si faltan datos por hora
sparse = [post("facebook", d, 19, 3000) for d in range(1, 13)]
r = insights.learn(sparse, now, tz, explore=False, n=3, defaults=DEF)["all"]
check("si solo hay una hora con datos, completa con las de siempre", r["enough"] and "19:30" in r["slots"] and len(r["slots"]) >= 2)
check("fechas con 'Z' y texto también se leen", insights._dt("2026-11-16T20:00:00Z").hour == 20 and insights._dt("basura") is None)

# ---- due_for_refresh
items = [{"network": "facebook", "external_id": "a", "published_at": at(0, 18, 0).isoformat()},
         {"network": "facebook", "external_id": "b", "published_at": at(1, 18, 0).isoformat()},
         {"network": "facebook", "external_id": "c", "published_at": at(10, 18, 0).isoformat()},
         {"network": "youtube", "external_id": "d", "published_at": at(2, 18, 0).isoformat()}]
stats = {("facebook", "b"): {"fetched_at": (now - timedelta(minutes=10)).isoformat()},
         ("facebook", "c"): {"fetched_at": (now - timedelta(hours=2)).isoformat()},
         ("youtube", "d"): {"fetched_at": (now - timedelta(minutes=120)).isoformat()}}
due = [i["external_id"] for i in insights.due_for_refresh(items, stats, now, minutes=60, batch=10)]
check("lo nunca leído va primero", due[0] == "a")
check("lo reciente leído hace 10 min espera", "b" not in due)
check("lo viejo (10 días) leído hace 2 h espera (cada 12 h)", "c" not in due)
check("lo reciente leído hace más de 60 min se vuelve a leer", "d" in due)
check("el tope por vuelta se respeta", len(insights.due_for_refresh(items, {}, now, batch=2)) == 2)


# ---- lectura de las redes (respuestas simuladas)
class R:
    def __init__(self, j, ok=True, text=""):
        self.j, self.ok, self.text = j, ok, text or str(j)

    def json(self):
        return self.j


config.FB_PAGE_TOKEN, config.FB_PAGE_ID, config.IG_TOKEN, config.IG_USER_ID = "tok", "page1", "igtok", "ig1"
calls = []


def fb_get(url, params=None, **k):
    calls.append((url, dict(params or {})))
    return R({"views": 4200, "likes": {"summary": {"total_count": 90}}, "comments": {"summary": {"total_count": 7}}})


s = insights.fetch_facebook("v1", get=fb_get)
check("Facebook: vistas, likes y comentarios", s == {"views": 4200, "likes": 90, "comments": 7, "shares": 0})
check("Facebook: pide el video correcto con el token", calls[0][0].endswith("/v1") and calls[0][1]["access_token"] == "tok")


def fb_noviews(url, params=None, **k):
    if url.endswith("/video_insights"):
        return R({"data": [{"values": [{"value": 777}]}]})
    if "views" in params["fields"]:
        return R({"error": {"message": "views no existe"}}, ok=False)
    return R({"likes": {"summary": {"total_count": 3}}, "comments": {"summary": {"total_count": 1}}})


s = insights.fetch_facebook("v1", get=fb_noviews)
check("Facebook sin 'views': usa video_insights", s["views"] == 777 and s["likes"] == 3 and s["comments"] == 1)
try:
    insights.fetch_facebook("v1", get=lambda *a, **k: R({"error": {"message": "token vencido"}}, ok=False))
    check("Facebook con error lanza", False)
except RuntimeError as e:
    check("Facebook con error lanza con el motivo", "token vencido" in str(e))


def ig_get(url, params=None, **k):
    if url.endswith("/insights"):
        return R({"data": [{"name": "views", "values": [{"value": 12000}]}, {"name": "shares", "values": [{"value": 31}]}]})
    return R({"like_count": 400, "comments_count": 22})


s = insights.fetch_instagram("m1", get=ig_get)
check("Instagram: vistas, likes, comentarios y compartidos", s == {"views": 12000, "likes": 400, "comments": 22, "shares": 31})
s = insights.fetch_instagram("m1", get=lambda url, params=None, **k: R({}, ok=False) if url.endswith("/insights") else R({"like_count": 5, "comments_count": 1}))
check("Instagram sin insights igual da likes y comentarios", s["likes"] == 5 and s["views"] == 0)

config.YT_API_KEY = "KEY"
seen = {}


def yt_get(url, params=None, headers=None, **k):
    seen.update(params)
    return R({"items": [{"id": "y1", "statistics": {"viewCount": "5000", "likeCount": "100", "commentCount": "9"}},
                        {"id": "y2", "statistics": {"viewCount": "10"}}]})


s = insights.fetch_youtube(["y1", "y2"], get=yt_get)
check("YouTube: lee varios videos de una vez", s["y1"]["views"] == 5000 and s["y1"]["likes"] == 100 and s["y2"]["likes"] == 0)
check("YouTube con YT_API_KEY usa la llave y pide los ids juntos", seen["key"] == "KEY" and seen["id"] == "y1,y2")
config.YT_API_KEY = ""

check("seguidores de Facebook", insights.fetch_followers("facebook", get=lambda *a, **k: R({"followers_count": 12345})) == 12345)
check("seguidores: si falla, None", insights.fetch_followers("facebook", get=lambda *a, **k: R({}, ok=False)) is None)
check("seguidores de Instagram", insights.fetch_followers("instagram", get=lambda *a, **k: R({"followers_count": 777})) == 777)


# ---- refresh y relearn con base simulada
class FakeDB:
    def __init__(self, items, stats=None, learning=()):
        self.items, self.stats, self.saved, self.learning, self.hours, self.followers = items, stats or {}, [], list(learning), {}, []

    def published_items(self, days):
        return self.items

    def stats_map(self):
        return self.stats

    def save_stats(self, rows):
        self.saved += rows

    def stats_for_learning(self, days):
        return self.learning

    def save_best_hours(self, net, rows):
        self.hours[net] = rows

    def save_followers(self, net, v):
        self.followers.append((net, v))


items = [{"network": "facebook", "external_id": "f1", "post_id": "p1", "clip_id": "c1", "published_at": at(1, 19, 0).isoformat()},
         {"network": "instagram", "external_id": "i1", "post_id": "p2", "clip_id": "c2", "published_at": at(1, 12, 0).isoformat()},
         {"network": "youtube", "external_id": "y1", "post_id": "p3", "clip_id": "c3", "published_at": at(1, 21, 0).isoformat()},
         {"network": "youtube", "external_id": "y2", "post_id": "p4", "clip_id": "c4", "published_at": at(1, 21, 0).isoformat()}]
fetchers = {"facebook": lambda i: {"views": 10, "likes": 1, "comments": 0, "shares": 0},
            "instagram": lambda i: 1 / 0,
            "youtube": lambda ids: {"y1": {"views": 55, "likes": 5, "comments": 1, "shares": 0}}}
d = FakeDB(items, stats={("instagram", "i1"): {"views": 300, "likes": 20, "comments": 2, "shares": 1, "fetched_at": (now - timedelta(hours=5)).isoformat()}})
n = insights.refresh(d, now, fetchers)
by = {(r["network"], r["external_id"]): r for r in d.saved}
check("guarda una fila por publicación leída", n == 4 and len(by) == 4)
check("Facebook guardado con ids de post y clip", by[("facebook", "f1")]["views"] == 10 and by[("facebook", "f1")]["clip_id"] == "c1" and by[("facebook", "f1")]["error"] is None)
check("un error NO borra lo que ya se sabía", by[("instagram", "i1")]["views"] == 300 and "division" in by[("instagram", "i1")]["error"])
check("YouTube se lee en lote y lo que falta queda con error", by[("youtube", "y1")]["views"] == 55 and by[("youtube", "y1")]["error"] is None)
check("YouTube sin respuesta de un video lo marca", by[("youtube", "y2")]["error"] is not None)

d = FakeDB(items, stats={})
insights.refresh(d, now, {"facebook": lambda i: 1 / 0, "instagram": lambda i: 1 / 0, "youtube": lambda ids: 1 / 0})
check("si todo falla no se cae y anota los errores", len(d.saved) == 4 and all(r["error"] for r in d.saved))

config.STATS_MINUTES = 60
d = FakeDB(items, stats={("facebook", "f1"): {"fetched_at": (now - timedelta(minutes=5)).isoformat()}})
insights.refresh(d, now, fetchers)
check("lo leído hace 5 min no se vuelve a pedir", ("facebook", "f1") not in {(r["network"], r["external_id"]) for r in d.saved})

config.LEARN_MIN_POSTS, config.LEARN_MIN_PER_HOUR = 12, 2
config.POST_TZ_OFFSET = -4
d = FakeDB([], learning=data)
res = insights.relearn(d, now)
check("relearn guarda las filas de cada red con datos", "all" in d.hours and "facebook" in d.hours and d.hours["all"])
check("relearn devuelve las horas elegidas", len(res["all"]) == 3)
d = FakeDB([], learning=few)
insights.relearn(d, now)
check("con pocos datos relearn limpia (se usan tus horas)", d.hours.get("all") == [])

# ---- tick respeta el interruptor
config.STATS = False
insights._last = 0
check("STATS=0: no hace nada", insights.tick(FakeDB(items)) == 0)
config.STATS = True

# ---- la cola usa las horas aprendidas
clips = [{"id": "a", "viral": {"score": 90}}]
base = autoqueue.plan(clips, {}, ["facebook"], now=now)
learned = autoqueue.plan(clips, {}, ["facebook"], now=now, slots={"facebook": ["20:30"]})
loc = datetime.fromisoformat(learned[0]["scheduled_at"]).astimezone(tz)
check("la cola usa la hora aprendida de esa red", (loc.hour, loc.minute) == (20, 30))
check("sin horas aprendidas usa POST_SLOTS", datetime.fromisoformat(base[0]["scheduled_at"]).astimezone(tz).hour in (21, 12, 19))
other = autoqueue.plan(clips, {}, ["facebook", "instagram"], now=now, slots={"facebook": ["20:30"]})
byn = {p["network"]: datetime.fromisoformat(p["scheduled_at"]).astimezone(tz) for p in other}
check("una red sin horas aprendidas conserva las suyas por defecto", (byn["facebook"].hour, byn["facebook"].minute) == (20, 30) and byn["instagram"].hour in (21, 12, 19))

# ======================================================================== Facebook como fuente
check("link de página", discover.fb_page_ref("https://www.facebook.com/AlofokeRadioShow/") == "AlofokeRadioShow")
check("link con id", discover.fb_page_ref("https://www.facebook.com/profile.php?id=100012345678") == "100012345678")
check("link /pages/Nombre/id", discover.fb_page_ref("https://facebook.com/pages/Algo/1234567890") == "1234567890")
check("solo el id", discover.fb_page_ref("100012345678") == "100012345678")
check("link sin https", discover.fb_page_ref("facebook.com/alofoke") == "alofoke")
check("link de un video no es una página", discover.fb_page_ref("https://www.facebook.com/watch/?v=123") is None)
check("link de otro sitio no sirve", discover.fb_page_ref("https://youtube.com/@x") is None and discover.fb_page_ref("") is None)

v = {"id": "55", "title": "", "description": "  Pelea   en vivo \n en la casa ", "permalink_url": "/AlofokeRadioShow/videos/55/", "length": 1800.5,
     "created_time": "2026-11-16T18:00:00+0000", "views": 9000, "live_status": "VOD"}
inf = discover.fb_info(v)
check("convierte un video de Facebook al formato de evaluate", inf["id"] == "55" and inf["duration"] == 1800.5 and inf["view_count"] == 9000)
check("título sale de la descripción si no hay", inf["title"] == "Pelea en vivo en la casa")
check("link relativo pasa a completo", inf["webpage_url"] == "https://www.facebook.com/AlofokeRadioShow/videos/55/")
check("fecha con +0000 se entiende", abs(inf["timestamp"] - datetime(2026, 11, 16, 18, 0, tzinfo=timezone.utc).timestamp()) < 1)
check("VOD no es directo", inf["live_status"] is None)
check("directo en curso se marca", discover.fb_info({**v, "live_status": "LIVE"})["live_status"] == "is_live")
check("sin views usa reacciones", discover.fb_info({**v, "views": None, "reactions": {"summary": {"total_count": 321}}})["view_count"] == 321)

ffeed = {"id": "ff", "name": "Alofoke FB", "kind": "facebook", "target": "https://www.facebook.com/AlofokeRadioShow", "min_minutes": 3,
         "max_minutes": 120, "max_age_hours": 48, "min_views": 0, "clips": 4}
t0 = datetime(2026, 11, 16, 20, 0, tzinfo=timezone.utc)
fstamp = lambda h: (t0 - timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%S+0000")  # noqa: E731
payload = {"data": [{"id": "1", "title": "A", "permalink_url": "/p/videos/1/", "length": 900, "created_time": fstamp(2), "views": 8000, "live_status": "VOD"},
                    {"id": "2", "title": "B", "permalink_url": "/p/videos/2/", "length": 900, "created_time": fstamp(100), "views": 9000},
                    {"id": "3", "title": "Directo", "permalink_url": "/p/videos/3/", "length": 0, "created_time": fstamp(1), "views": 10, "live_status": "LIVE"},
                    {"title": "sin id"}]}
seen = []


def fb_list_get(url, params=None, **k):
    seen.append((url, dict(params)))
    return R(payload)


config.FB_PAGE_TOKEN = "tok"
cands = discover.fb_list(ffeed, 8, get=fb_list_get)
check("lista los videos de la página con su info", [c["id"] for c in cands] == ["1", "2", "3"] and cands[0]["info"]["view_count"] == 8000)
check("llama a /<página>/videos con el token", seen[0][0].endswith("/AlofokeRadioShow/videos") and seen[0][1]["access_token"] == "tok")
check("inspect no llama a yt-dlp si ya hay info", discover.inspect(cands[0]) is cands[0]["info"])

calls2 = []


def fb_fallback(url, params=None, **k):
    calls2.append(params["fields"])
    return R({"error": {"message": "no views"}}, ok=False) if "views" in params["fields"] else R(payload)


check("si un campo no está permitido, reintenta con lo básico", len(discover.fb_list(ffeed, 8, get=fb_fallback)) == 3 and len(calls2) == 2)
for code, expect in ((190, "venció"), (10, "Page Public Content Access"), (100, "error")):
    try:
        discover.fb_list(ffeed, 8, get=lambda *a, **k: R({"error": {"code": code, "message": "m"}}, ok=False))
        check("error de Facebook lanza", False)
    except RuntimeError as e:
        check(f"error {code} se explica", expect in str(e))
config.FB_PAGE_TOKEN = ""
try:
    discover.fb_list(ffeed, 8, get=fb_list_get)
    check("sin token lanza", False)
except RuntimeError as e:
    check("sin FB_PAGE_TOKEN lo dice", "FB_PAGE_TOKEN" in str(e))
config.FB_PAGE_TOKEN = "tok"
try:
    discover.fb_list({**ffeed, "target": "https://youtube.com/x"}, 8, get=fb_list_get)
    check("link raro lanza", False)
except RuntimeError as e:
    check("link que no es de Facebook se rechaza con motivo", "link" in str(e))


# ---- vuelta completa con una fuente de Facebook
class FDB:
    def __init__(self):
        self.created, self.skipped, self.updates = [], [], []

    def now(self):
        return "NOW"

    def due_feeds(self, m):
        return [ffeed]

    def discovered_today(self):
        return len(self.created)

    def videos_waiting(self):
        return len(self.created)

    def known_video_ids(self, fid, ids):
        return set()

    def url_already_used(self, u):
        return False

    def remember_video(self, fid, i, status, reason=None, sid=None):
        self.skipped.append((i["id"], reason))

    def create_vod_source(self, f, i):
        self.created.append(i)

    def update_feed(self, fid, **f):
        self.updates.append(f)


config.DISCOVER, config.DISCOVER_MAX_PER_DAY, config.DISCOVER_MAX_QUEUED, config.DISCOVER_INSPECT = True, 4, 2, 6
discover._last = 0
fd = FDB()
q = discover.tick(fd, lambda f: discover.fb_list(f, 8, get=fb_list_get), discover.inspect, t0)
check("vuelta completa: encola el video bueno de Facebook", q == 1 and [i["id"] for i in fd.created] == ["1"])
check("el video de Facebook lleva su link para yt-dlp", fd.created[0]["webpage_url"] == "https://www.facebook.com/p/videos/1/")
check("el viejo y el directo se anotan como saltados", ("2", "ya es viejo") in fd.skipped and any(i == "3" for i, _ in fd.skipped))
check("estado de la fuente", fd.updates[-1]["last_status"] == "1 nuevo(s)")

fd = FDB()
discover._last = 0
discover.tick(fd, lambda f: discover.fb_list(f, 8, get=lambda *a, **k: R({"error": {"code": 190, "message": "x"}}, ok=False)), discover.inspect, t0)
check("si Facebook da error, la fuente muestra el motivo y no se cae", fd.updates[-1]["last_status"].startswith("error:") and fd.created == [])

# ======================================================================== Conectar cuentas (llaves guardadas en la web)
import connections  # noqa: E402

rows = [{"network": "facebook", "data": {"page_id": " 123456 ", "page_token": "FBTOK"}},
        {"network": "youtube", "data": {"client_id": "cid", "client_secret": "sec", "refresh_token": "ref", "api_key": ""}},
        {"network": "otra", "data": {"x": "1"}}]
o = connections.overlay(rows, environ={})
check("pasa las llaves de la web a config (sin espacios)", o["FB_PAGE_ID"] == "123456" and o["FB_PAGE_TOKEN"] == "FBTOK" and o["YT_REFRESH_TOKEN"] == "ref")
check("un campo vacío no pisa nada y una red rara se ignora", "YT_API_KEY" not in o and len(o) >= 5)
check("Instagram usa el token de Facebook si no tiene el suyo", o["IG_TOKEN"] == "FBTOK")
o = connections.overlay(rows + [{"network": "instagram", "data": {"user_id": "9", "token": "IGTOK"}}], environ={})
check("con token propio de Instagram, usa ese", o["IG_TOKEN"] == "IGTOK" and o["IG_USER_ID"] == "9")
check("si IG_TOKEN ya está en .env no lo pisa con el de Facebook", "IG_TOKEN" not in connections.overlay(rows, environ={"IG_TOKEN": "ENV"}))
check("sin filas no cambia nada", connections.overlay([], environ={}) == {} and connections.overlay(None, environ={}) == {})
config.FB_PAGE_ID = ""
connections.apply(rows)
check("apply() pone los valores en config", config.FB_PAGE_ID == "123456")
config.FB_PAGE_ID = ""

print(f"OK: {ok} comprobaciones")
