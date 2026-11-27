"""Parte 9: clips automáticos de lo mejor del momento. Ejecuta: python test_parte9.py"""
from datetime import datetime, timedelta, timezone

import config
import discover

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


now = datetime(2026, 11, 16, 20, 0, tzinfo=timezone.utc)
ts = lambda h: (now - timedelta(hours=h)).timestamp()  # noqa: E731
feed = {"id": "f1", "name": "Alofoke", "kind": "channel", "target": "https://youtube.com/@x", "min_minutes": 3, "max_minutes": 120,
        "max_age_hours": 48, "min_views": 0, "clips": 4}


def info(**k):
    return {"id": "v", "title": "t", "duration": 1800, "timestamp": ts(5), "view_count": 5000, "webpage_url": "https://youtu.be/v", **k}


# ---- evaluate
s, why, vel = discover.evaluate(info(), feed, now)
check("video normal sirve", s and why == "" and vel == 1000.0)                      # 5000 vistas / 5 h
check("directo en curso no", not discover.evaluate(info(is_live=True), feed, now)[0])
check("directo programado no", not discover.evaluate(info(live_status="is_upcoming"), feed, now)[0])
check("directo que ya terminó sí", discover.evaluate(info(live_status="was_live"), feed, now)[0])
check("muy corto no", discover.evaluate(info(duration=60), feed, now)[1] == "muy corto")
check("muy largo no", "muy largo" in discover.evaluate(info(duration=3 * 3600), feed, now)[1])
check("viejo no", discover.evaluate(info(timestamp=ts(100)), feed, now)[1] == "ya es viejo")
check("sin fecha no", not discover.evaluate(info(timestamp=None), feed, now)[0])
check("pocas vistas no", discover.evaluate(info(view_count=10), {**feed, "min_views": 100}, now)[1].startswith("pocas vistas"))
check("recién subido no divide entre 0", discover.evaluate(info(timestamp=ts(0.01)), feed, now)[2] == 5000.0)
check("fecha del futuro no", not discover.evaluate(info(timestamp=ts(-5)), feed, now)[0])
check("más vistas por hora = más velocidad", discover.evaluate(info(view_count=9000), feed, now)[2] > vel)

# ---- pick
check("pick ordena por velocidad", [i["id"] for i in discover.pick([(10, {"id": "a"}), (500, {"id": "b"}), (50, {"id": "c"})], 2)] == ["b", "c"])
check("pick con 0 o negativo = nada", discover.pick([(1, {"id": "a"})], 0) == [] and discover.pick([(1, {"id": "a"})], -3) == [])


# ---- tick con base simulada
class FakeDB:
    def __init__(self, today=0, waiting=0, used=(), known=()):
        self.today, self.wait, self.used, self.known = today, waiting, set(used), set(known)
        self.created, self.skipped, self.updates = [], [], []

    def now(self):
        return "NOW"

    def due_feeds(self, m):
        return [feed]

    def discovered_today(self):
        return self.today + len(self.created)

    def videos_waiting(self):
        return self.wait + len(self.created)

    def known_video_ids(self, fid, ids):
        return {i for i in ids if i in self.known}

    def url_already_used(self, u):
        return u in self.used

    def remember_video(self, fid, i, status, reason=None, sid=None):
        self.skipped.append((i["id"], reason))

    def create_vod_source(self, f, i):
        self.created.append(i["id"])

    def update_feed(self, fid, **f):
        self.updates.append(f)


VID = {f"v{i}": info(id=f"v{i}", title=f"Video {i}", view_count=1000 * (i + 1), webpage_url=f"https://youtu.be/v{i}") for i in range(4)}
lister = lambda f: [{"id": k, "url": v["webpage_url"], "title": v["title"]} for k, v in VID.items()]  # noqa: E731
inspector = lambda c: VID[c["id"]]  # noqa: E731

config.DISCOVER = False
discover._last = 0
check("apagado: no hace nada", discover.tick(FakeDB(), lister, inspector, now) == 0)

config.DISCOVER, config.DISCOVER_MAX_PER_DAY, config.DISCOVER_MAX_QUEUED, config.DISCOVER_INSPECT = True, 4, 2, 6
d = FakeDB()
check("encola hasta el tope de espera (2)", discover.tick(d, lister, inspector, now) == 2)
check("elige los de más vistas por hora", d.created == ["v3", "v2"])
check("anota estado de la fuente", d.updates[-1]["last_status"] == "2 nuevo(s)" and d.updates[-1]["last_checked"] == "NOW")

d = FakeDB(today=4)
check("tope diario: no encola", discover.tick(d, lister, inspector, now) == 0 and d.updates[-1]["last_status"] == "sin cupo hoy")
d = FakeDB(waiting=2)
check("ya hay videos esperando: no apila", discover.tick(d, lister, inspector, now) == 0)
d = FakeDB(known=["v3", "v2", "v1", "v0"])
check("lo ya visto no se repite", discover.tick(d, lister, inspector, now) == 0 and d.updates[-1]["last_status"] == "nada nuevo")
d = FakeDB(used=["https://youtu.be/v3"])
discover.tick(d, lister, inspector, now)
check("si ya lo clipeaste a mano, lo salta y lo anota", "v3" not in d.created and ("v3", "ya lo tienes en tu biblioteca") in d.skipped)

VID["v1"] = info(id="v1", duration=30, webpage_url="https://youtu.be/v1")
d = FakeDB()
discover.tick(d, lister, inspector, now)
check("video corto se anota como saltado", ("v1", "muy corto") in d.skipped and "v1" not in d.created)

d = FakeDB()
discover.tick(d, lister, lambda c: None, now)
check("si no se puede leer un video, no lo marca (reintenta luego)", d.created == [] and d.skipped == [])

check("error del listado no tumba", discover.tick(FakeDB(), lambda f: 1 / 0, inspector, now) == 0)

config.DISCOVER_MAX_PER_DAY, config.DISCOVER_MAX_QUEUED = 4, 9
VID["v0"]["view_count"] = 3
d = FakeDB()
discover.tick(d, lister, inspector, now)
feed["min_views"] = 100
d = FakeDB()
discover.tick(d, lister, inspector, now)
check("'pocas vistas' NO se marca (se reconsidera después)", all(r != "pocas vistas (3)" for _, r in d.skipped) and "v0" not in d.created)
feed["min_views"] = 0

print(f"OK: {ok} comprobaciones")
