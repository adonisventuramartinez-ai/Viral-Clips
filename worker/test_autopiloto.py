"""Piloto automático multi-proyecto: config desde la web, páginas y publicación firmada.
Ejecuta: python test_autopiloto.py"""
import hashlib
import hmac
import json
import sys
import types
import urllib.request

import autoqueue
import config
import poster

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *a, **k: object())   # sin red ni llaves reales
import db  # noqa: E402


class Q:
    """Supabase simulado para la fila connections.network='autopilot' (respaldo local)."""

    def __init__(self, rows=None):
        self.rows, self.reads = rows or [], 0

    def table(self, name):
        assert name == "connections"
        return self

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        self.reads += 1
        return types.SimpleNamespace(data=self.rows)


def use(data=None):
    db.sb = Q([{"data": data}] if data is not None else [])
    db._ap["at"] = 0.0


config.WEB_URL = ""          # primero probamos el respaldo local, sin HTTP
config.R2_SECRET_ACCESS_KEY = "secreto-tigris-de-prueba"

check("redes internas por página", autoqueue.autopilot_networks(["123", "456", "x"]) == ["facebook:123", "facebook:456"])
check("parseo de red con página", poster.fb_page_of("facebook:123") == "123" and poster.fb_page_of("facebook") is None)

use({"enabled": True, "page_ids": ["123", "456", "123", "x"], "auto_approve": True, "max_per_run": 7})
cfg = db.autopilot_config()
check("config del piloto y dedupe de páginas", cfg == {"enabled": True, "page_ids": ["123", "456"], "auto_approve": True, "max_per_run": 7})
check("lee Supabase una sola vez en la ventana", db.autopilot_config()["page_ids"] == ["123", "456"] and db.sb.reads == 1)

use({"enabled": "false", "page_ids": [], "max_per_run": "mal"})
cfg = db.autopilot_config()
check("valores raros no tumban al worker", cfg == {"enabled": False, "page_ids": [], "auto_approve": True, "max_per_run": 5})
check("sin fila el piloto queda apagado", (use(), db.autopilot_on())[1] is False)


# ---- la config de la WEB gana sobre el respaldo local, firmada con la llave R2/Tigris
class Resp:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


sent = {}


def fake_urlopen(req, timeout=None):
    raw = req.data.decode()
    sent["url"] = req.full_url
    sent["body"] = json.loads(raw)
    sent["firma"] = req.get_header("X-autopiloto")
    esperada = hmac.new(config.R2_SECRET_ACCESS_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()
    check("firma HMAC con la llave R2/Tigris", sent["firma"] == esperada)
    if req.full_url.endswith("/api/autopiloto/publicar"):
        return Resp({"ok": True, "id": "vid_1"})
    return Resp({"ok": True, "config": {"enabled": True, "page_ids": ["999"], "auto_approve": True, "max_per_run": 3}})


urllib.request.urlopen = fake_urlopen
config.WEB_URL = "https://ejemplo.vercel.app"
db._ap["at"] = 0.0
cfg = db.autopilot_config()
check("la web manda las páginas (BD distinta)", cfg["page_ids"] == ["999"] and cfg["max_per_run"] == 3)
check("el worker pide la config con POST", sent["body"] == {"worker": True})


# ---- aprobación automática real: los 'ready' pasan a 'approved'
class ClipsQ:
    def __init__(self):
        self.updated = None

    def table(self, name):
        self.name = name
        return self

    def select(self, *a, **k):
        return self

    def in_(self, col, vals):
        self.vals = vals
        return self

    def gte(self, *a, **k):
        return self

    @property
    def not_(self):
        return types.SimpleNamespace(is_=lambda *a, **k: self)

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def update(self, fields):
        self.updated = fields
        return self

    def __getattr__(self, n):
        return lambda *a, **k: self

    def execute(self):
        if getattr(self, "name", "clips") == "posts" or self.updated is not None:
            return types.SimpleNamespace(data=[])
        return types.SimpleNamespace(data=[
            {"id": "clip1", "viral_status": "ready", "publish_status": None, "storage_path": "x/y.mp4"},
            {"id": "clip2", "viral_status": "ready", "publish_status": None, "storage_path": "x/z.mp4"},
        ])


q = ClipsQ()
db.sb = q
db.require_approval = lambda: True
rows = db.clips_ready_for_autopilot(["123"], 5, auto_approve=True)
check("aprobación automática en el piloto", q.updated == {"viral_status": "approved"} and len(rows) == 2)


# ---- publicación por página: la web recibe el id de página y firma con R2/Tigris
vid = poster.publish_to_page("123", {"id": "post_1"}, {"storage_path": "source/clip.mp4", "title": "Hola", "description": "Mundo"})
check("la web publica en la página elegida", vid == "vid_1" and sent["url"].endswith("/api/autopiloto/publicar"))
check("el worker manda página y archivo", sent["body"]["page_id"] == "123" and sent["body"]["storage_path"] == "source/clip.mp4")
config.R2_SECRET_ACCESS_KEY = ""
sin_llave = False
try:
    poster.publish_to_page("123", {}, {"storage_path": "x.mp4"})
except RuntimeError:
    sin_llave = True
check("sin llave R2 el worker no publica", sin_llave)

print(f"AUTOPILOTO OK ({ok} pruebas)")
