"""Mejora 4: cola con reintentos y prioridades, logs claros, plantillas de marca y vista previa. Sin internet. Ejecuta: python test_mejora4.py"""
import io
import subprocess
import sys
import tempfile
import types
from pathlib import Path

import config
import jobq
import logx

# ---------- errores explicados y reintentos
cases = [
    (RuntimeError("Sign in to confirm you're not a bot"), False, "cookies"),
    (RuntimeError("Video unavailable. This video has been removed"), False, "ya no está"),
    (RuntimeError("No se detectó voz en el video"), False, "voz"),
    (RuntimeError("La IA no encontró momentos para clips"), False, "momentos"),
    (RuntimeError("HTTP Error 429: Too Many Requests"), True, "límite"),
    (ConnectionError("Connection reset by peer"), True, "conexión"),
    (OSError(28, "No space left on device"), False, "disco"),
    (MemoryError("Cannot allocate memory"), True, "memoria"),
    (RuntimeError("ffmpeg falló: Invalid data found when processing input"), True, "ffmpeg"),
    (ValueError("algo rarísimo"), True, "inesperado"),
]
for exc, retry, word in cases:
    msg, r = jobq.explain(exc)
    assert r is retry, (exc, r)
    assert word in msg.lower(), (exc, msg)
assert jobq.explain(RuntimeError("El clip ya no existe"))[0] == "El clip ya no existe"      # mensajes propios, tal cual

config.JOB_RETRY_DELAYS = [60, 300, 900]
assert [jobq.delay_for(i) for i in (1, 2, 3, 4, 0)] == [60, 300, 900, 900, 60]
d = jobq.decide({"attempts": 1, "max_attempts": 3}, ConnectionError("timed out"))
assert d["retry"] and d["delay"] == 60 and "timed out" in d["detail"]
d = jobq.decide({"attempts": 3, "max_attempts": 3}, ConnectionError("timed out"))
assert not d["retry"] and "3 veces" in d["message"]                                          # agotó los intentos
d = jobq.decide({"attempts": 1}, RuntimeError("No se detectó voz"))
assert not d["retry"] and d["delay"] == 0                                                     # error que no se arregla solo
assert jobq.priority_of("record") > jobq.priority_of("clip") > jobq.priority_of("download")
assert jobq.priority_of("download", urgent=True) > jobq.priority_of("download")
print("OK: mejora 4, errores y reintentos")

# ---------- cola (Supabase simulado)
class Q:
    def __init__(self, sb, name):
        self.sb, self.name, self.ops, self.data = sb, name, [], None

    def __getattr__(self, op):
        def f(*a, **k):
            self.ops.append((op, a, k))
            return self
        return f

    def execute(self):
        self.sb.log.append((self.name, self.ops))
        if any(o == "or_" for o, *_ in self.ops) and self.sb.no_cols:
            raise RuntimeError("column jobs.priority does not exist")
        if any(o == "update" and "last_error" in a[0] for o, a, _ in self.ops) and self.sb.no_cols:
            raise RuntimeError("column last_error does not exist")
        r = types.SimpleNamespace(data=[])
        kinds = [o for o, *_ in self.ops]
        if "select" in kinds:
            r.data = list(self.sb.rows.get(self.name, []))
        elif "update" in kinds:
            r.data = [{"id": "j1", "attempts": 1}]
        return r


class SB:
    def __init__(self, rows=None, no_cols=False):
        self.rows, self.no_cols, self.log = rows or {}, no_cols, []

    def table(self, name):
        return Q(self, name)


fake = types.ModuleType("supabase")
holder = {}
fake.create_client = lambda *a, **k: holder.setdefault("sb", SB())
sys.modules["supabase"] = fake
config.SUPABASE_URL, config.SUPABASE_KEY = "http://x", "k"
import db  # noqa: E402

db.sb = SB({"jobs": [{"id": "j1", "attempts": 0, "type": "download"}]})
job = db.claim_job()
ops = [o for n, ops in db.sb.log for o, *_ in ops]
assert job and ops.count("order") == 2 and "or_" in ops                                        # prioridad + fecha + run_after
order_cols = [a[0] for n, o in db.sb.log[:1] for op, a, k in o if op == "order"]
assert order_cols == ["priority", "created_at"], order_cols

db._queue_cols_ok = True
db.sb = SB({"jobs": [{"id": "j1", "attempts": 0, "type": "download"}]}, no_cols=True)
assert db.claim_job() and db._queue_cols_ok is False                                           # sin la migración: sigue funcionando
db.finish_job("j1", ok=False, error="boom")                                                    # y no revienta con last_error ausente
db.retry_job("j1", 60, error="boom")
db._queue_cols_ok = True

db.sb = SB()
db.retry_job("j1", 120, error="x")
upd = [a[0] for n, o in db.sb.log for op, a, k in o if op == "update"][0]
assert upd["status"] == "queued" and upd["locked_at"] is None and upd["run_after"] and upd["last_error"] == "x"

# trabajos interrumpidos: reintentar o dejar en error si ya agotaron intentos
db.sb = SB({"jobs": [{"id": "a", "attempts": 1, "source_id": "s1"}, {"id": "b", "attempts": 3, "source_id": "s2"}]})
db.requeue_stale()
ups = [(a[0].get("status"), [x for x in o if x[0] == "eq"][-1][1]) for n, o in db.sb.log for op, a, k in o if op == "update"]
assert ("queued", ("id", "a")) in ups and ("error", ("id", "b")) in ups, ups
print("OK: mejora 4, cola")

# ---------- reintento sin duplicados
db.sb = SB({"clips": [{"id": "c1", "storage_path": "s/c1.mp4", "thumb_path": "t/c1.jpg", "publish_status": None},
                      {"id": "c2", "storage_path": "s/c2.mp4", "thumb_path": None, "publish_status": "published"}]})
assert db.reset_source_outputs("s1") == 1                                                      # borra el clip a medias, respeta el publicado
deleted = [[x for x in o if x[0] == "eq"][0][1][1] for n, o in db.sb.log if n == "clips" and any(op == "delete" for op, *_ in o)]
assert deleted == ["c1"]
assert {n for n, o in db.sb.log} >= {"transcript_segments", "rejected_moments"}
print("OK: mejora 4, reintento sin duplicados")

# ---------- logs
real = io.StringIO()
old = sys.stdout
config.LOG_DIR = Path(tempfile.mkdtemp())
tee = logx._Tee(real)
logx._installed = True
import logging  # noqa: E402
from logging.handlers import RotatingFileHandler  # noqa: E402
h = RotatingFileHandler(config.LOG_DIR / "worker.log", encoding="utf-8")
h.setFormatter(logging.Formatter("%(message)s"))
logx._file_logger = logging.getLogger("t4")
logx._file_logger.addHandler(h)
logx._file_logger.setLevel(logging.INFO)
logx._file_logger.propagate = False
sys.stdout = tee
try:
    with logx.job("abcdef123456", "download"):
        print("hola\nsegunda línea", flush=True)
    print("suelta", flush=True)
finally:
    sys.stdout = old
h.flush()
lines = real.getvalue().splitlines()
assert lines[0][2] == ":" and "[download abcdef] hola" in lines[0] and "[download abcdef] segunda línea" in lines[1], lines
assert "Fin del trabajo" in lines[2] and "[" not in lines[3].split(" ", 1)[1][:1] and "suelta" in lines[3], lines
assert "hola" in (config.LOG_DIR / "worker.log").read_text(encoding="utf-8")
assert logx.fmt_dur(5) == "5 s" and logx.fmt_dur(125) == "2 min 05 s" and logx.fmt_dur(3725) == "1 h 02 min"
s = logx.Stages()
sys.stdout = io.StringIO()
s.begin("a"); s.begin("b")
summ = s.summary()
sys.stdout = old
assert summ.startswith("a 0 s · b 0 s"), summ
print("OK: mejora 4, logs")

# ---------- plantillas de marca
import brand  # noqa: E402

main_cfg = {"pos": "bc", "size": 24, "hook": True}
tpls = {"items": {"alofoke": {"name": "Alofoke", "settings": {"pos": "tr", "size": 12, "subs": {"active": "00E676"}}}}}
c, name = brand.pick_settings("alofoke", main_cfg, tpls)
assert name == "Alofoke" and c["pos"] == "tr" and c["subs"]["active"] == "00E676"
c, name = brand.pick_settings("no-existe", main_cfg, tpls)
assert name is None and c is main_cfg                                                          # plantilla borrada: marca general
assert brand.pick_settings(None, main_cfg, tpls)[1] is None and brand.pick_settings("x", main_cfg, {})[0] is main_cfg

calls = []
brand._read_json = lambda path: calls.append(path) or ({"pos": "br"} if path.endswith("settings.json") else tpls)
out = brand.load(Path(tempfile.mkdtemp()), template="alofoke")
assert out["pos"] == "tr" and out["subs"]["active"] == "00E676" and out["size"] == 12
config.LOGO_PATH = ""   # sin el logo de respaldo del .env
out = brand.load(Path(tempfile.mkdtemp()))
assert out["pos"] == "br" and calls[-1].endswith("settings.json")                              # sin plantilla no lee templates.json
print("OK: mejora 4, plantillas de marca")

# ---------- vista previa
import preview  # noqa: E402

assert preview.to_seconds("1:23") == 83 and preview.to_seconds("1:02:03") == 3723 and preview.to_seconds("90") == 90
assert preview.to_seconds("") == 60 and preview.to_seconds("a:b") == 60 and preview.to_seconds("1:2:3:4", 5) == 5 and preview.to_seconds("-3") == 60

tmp = Path(tempfile.mkdtemp())
vid = tmp / "v.mp4"
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30",
                "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=16000", "-t", "10", "-c:v", "libx264", "-preset", "ultrafast",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(vid)], check=True)
words = [{"w": w, "start": 1.0 + i * 0.4, "end": 1.35 + i * 0.4} for i, w in enumerate("esto es una prueba de los subtítulos".split())]
jpg = preview.make_preview(vid, words, 0.0, 6.0, tmp, tmp / "p.jpg", layout="crop", brand_cfg={"hook": True, "hook_sec": 3.5},
                           hook="Así se ve el gancho", opts={"zoom": "1", "tighten": "1"})
from PIL import Image  # noqa: E402
assert jpg.exists() and Image.open(jpg).size == (1080, 1920) and jpg.stat().st_size > 8000
assert not (tmp / "preview.mp4").exists()                                                      # no deja el video intermedio
try:
    preview.extract_frame(tmp / "no_existe.mp4", 1.0, tmp / "x.jpg")
    raise SystemExit("debía fallar")
except RuntimeError:
    pass
print("OK: mejora 4, vista previa")
print("TODAS LAS PRUEBAS DE LA MEJORA 4 PASARON")
