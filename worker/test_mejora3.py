"""Mejora 3: paquete de publicación, miniatura y programación. Ejecuta: python test_mejora3.py"""
import subprocess
import sys
import tempfile
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
import packager
import scheduler
import thumb

# ---------- packager
raw = {"tiktok": {"caption": "x " * 200, "hashtags": ["viral", "#Viral", "con espacio", "#a"] + [f"#t{i}" for i in range(9)]},
       "reels": {"caption": "Línea uno\n\nLínea dos\nLínea tres\nLínea cuatro", "hashtags": ["#r1"]},
       "shorts": {"title": "T" * 150, "description": "d" * 500, "hashtags": ["#x"]},
       "hooks": ["¡No lo vas a creer!", "no lo vas a creer!", "Mi título", "", "Otro gancho más", "Tercero", "Cuarto"],
       "first_comment": "¿Quién tiene la razón?"}
p = packager.clean_pack(raw, "Mi título", ["#base"])
assert len(p["tiktok"]["caption"]) <= packager.TIKTOK_CAP + 1, p["tiktok"]["caption"]
assert "#fyp" in p["tiktok"]["hashtags"] and len(p["tiktok"]["hashtags"]) <= 5
assert len({t.lower() for t in p["tiktok"]["hashtags"]}) == len(p["tiktok"]["hashtags"])      # sin repetidos (viral/#Viral)
assert all(t.startswith("#") and " " not in t for t in p["tiktok"]["hashtags"])
assert p["reels"]["caption"].count("\n") <= 2 and "cuatro" not in p["reels"]["caption"]
assert len(p["shorts"]["title"]) <= packager.SHORTS_TITLE + 1 and "#Shorts" in p["shorts"]["hashtags"]
assert p["hooks"][0] == "¡No lo vas a creer!" and len(p["hooks"]) == 3
assert "Mi título" not in p["hooks"] and len({h.lower() for h in p["hooks"]}) == 3          # sin copias ni el título
assert packager.clean_pack(None, "T")["shorts"]["title"] == "T"                                # basura -> paquete completo igual

fb = packager.fallback_pack("Pelea en vivo", "Se armó", ["#alofoke"], "MIRA ESTO")
assert fb["source"] == "plantilla" and fb["hooks"][0] == "MIRA ESTO" and fb["reels"]["caption"].endswith("👇")

# IA simulada: respuesta buena, respuesta rota y caída total
import llm
good = {"tiktok": {"caption": "Esto se salió de control", "hashtags": ["#drama"]},
        "reels": {"caption": "Mira lo que pasó\n¿Tú qué piensas?", "hashtags": ["#drama"]},
        "shorts": {"title": "Se salió de control", "description": "Resumen.", "hashtags": ["#drama"]},
        "hooks": ["Nadie lo vio venir", "¿Quién tiene la razón?", "Lo que dijo cambia todo"], "first_comment": "¿Equipo A o B?"}
orig_ask = llm.ask
llm.ask = lambda prompt, check=None: good
r = packager.build_pack({"title": "Pelea", "hook": "x", "hashtags": ["#a"]}, "texto", {"show": "Show"})
assert r["source"] == "ia" and r["hooks"][0] == "Nadie lo vio venir"
llm.ask = lambda prompt, check=None: {"tiktok": {}, "hooks": []}                   # IA sin hooks -> plantilla
assert packager.build_pack({"title": "Pelea"}, "t")["source"] == "plantilla"
def boom(*a, **k):
    raise RuntimeError("sin cupo")
llm.ask = boom
assert packager.build_pack({"title": "Pelea"}, "t")["source"] == "plantilla"
llm.ask = orig_ask
assert packager.caption_for({"pack": good and packager.clean_pack(good, "T")}, "shorts").startswith("Se salió de control\nResumen.")
assert packager.caption_for({"title": "Viejo", "description": "Desc", "hashtags": ["#a", "#b"]}) == "Desc\n#a #b"   # clips viejos
print("OK: mejora 3, paquete de publicación")

# ---------- miniatura
assert thumb.score_frame(300, 0.3, 0.5, 120) > thumb.score_frame(300, None, None, 120) > thumb.score_frame(20, None, None, 120)
assert thumb.score_frame(300, 0.3, 0.5, 120) > thumb.score_frame(300, 0.3, 0.9, 120)        # cara en el borde vale menos
assert thumb.score_frame(300, 0.3, 0.5, 10) < thumb.score_frame(300, 0.3, 0.5, 120)         # muy oscuro vale menos
tmp = Path(tempfile.mkdtemp())
vid = tmp / "v.mp4"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30", "-t", "8",
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(vid)], check=True)
t = thumb.pick_time(vid)
assert 0.5 <= t <= 7.5, t
out = thumb.make(vid, "¡Nadie esperaba lo que dijo el invitado sobre la resistencia!", tmp / "t.jpg")
assert out and out.exists() and out.stat().st_size > 5000
from PIL import Image
assert Image.open(out).size == (1080, 1920)
assert not list(tmp.glob("*.raw.jpg"))
assert thumb.make(tmp / "no_existe.mp4", "x", tmp / "n.jpg") is None                         # nunca revienta
print("OK: mejora 3, miniatura")

# ---------- programación
now = datetime.now(timezone.utc)
iso = lambda d: d.isoformat().replace("+00:00", "Z")  # noqa: E731
assert scheduler.is_due({"publish_status": "scheduled", "scheduled_at": iso(now - timedelta(minutes=1))})
assert not scheduler.is_due({"publish_status": "scheduled", "scheduled_at": iso(now + timedelta(minutes=5))})
assert not scheduler.is_due({"publish_status": "published", "scheduled_at": iso(now - timedelta(hours=1))})
assert not scheduler.is_due({"publish_status": "scheduled", "scheduled_at": "basura"})
assert not scheduler.is_due({"publish_status": "scheduled"})


class FakeDB:
    def __init__(self, rows):
        self.rows, self.log = rows, []

    def due_clips(self, limit=5):
        return [r for r in self.rows if scheduler.is_due(r)]

    def download_clip(self, path):
        return b"video"

    def update_clip(self, cid, **f):
        self.log.append((cid, f))
        for r in self.rows:
            if r["id"] == cid:
                r.update(f)


class FakePub:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, []

    def publish_reel(self, path, text):
        assert Path(path).read_bytes() == b"video"
        self.calls.append(text)
        return "123" if self.ok else None


row = {"id": "c1", "title": "T", "storage_path": "a/b.mp4", "description": "Desc", "hashtags": ["#a"],
       "publish_status": "scheduled", "scheduled_at": iso(now - timedelta(minutes=2))}
db_, pub = FakeDB([row]), FakePub(True)
assert scheduler.publish_one(row, db_, pub, tmp / "s") is True
assert row["publish_status"] == "published" and row["fb_video_id"] == "123" and pub.calls == ["Desc\n#a"]
assert db_.log[0][1]["publish_status"] == "error"          # se marca ANTES de publicar (si el worker se cae no repite)
assert db_.due_clips() == []                                # y ya no vuelve a salir como pendiente
row2 = {"id": "c2", "title": "T", "storage_path": "a/c.mp4", "publish_status": "scheduled", "scheduled_at": iso(now - timedelta(minutes=2))}
db2, pub2 = FakeDB([row2]), FakePub(False)
assert scheduler.publish_one(row2, db2, pub2, tmp / "s") is False
assert row2["publish_status"] == "error" and row2["publish_error"]
assert not list((tmp / "s").glob("*.mp4")), "dejó el archivo temporal"
config.FB_PAGE_ID = config.FB_PAGE_TOKEN = ""
assert scheduler.tick(FakeDB([row]), FakePub()) == 0       # sin credenciales no hace nada
print("OK: mejora 3, programación")
