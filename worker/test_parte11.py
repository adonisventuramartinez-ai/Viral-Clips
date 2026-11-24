"""Parte 11: worker siempre activo (Docker). Ejecuta: python test_parte11.py"""
import os
import subprocess
import sys
import tempfile
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

tmp = Path(tempfile.mkdtemp())
os.environ["ALIVE_FILE"] = str(tmp / "alive")

import config  # noqa: E402
import lifecycle  # noqa: E402

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


tz = timezone(timedelta(hours=-4))
at = lambda h: datetime(2026, 11, 17, h, 5, tzinfo=tz)  # noqa: E731
H = 3600

# ---- reinicio diario
check("a la hora, libre y con 20 h encendido: reinicia", lifecycle.should_restart(21 * H, at(4), True, True, 4))
check("justo 20 h también", lifecycle.should_restart(20 * H, at(4), True, True, 4))
check("recién arrancado: no (evita reiniciar en bucle)", not lifecycle.should_restart(10 * 60, at(4), True, True, 4))
check("otra hora: no", not lifecycle.should_restart(30 * H, at(15), True, True, 4))
check("ocupado: no", not lifecycle.should_restart(30 * H, at(4), False, True, 4))
check("publicando o por publicar: no", not lifecycle.should_restart(30 * H, at(4), True, False, 4))
check("RESTART_HOUR=-1 lo apaga", not lifecycle.should_restart(30 * H, at(4), True, True, -1) and not lifecycle.should_restart(30 * H, at(4), True, True, None))
check("la hora se mide en tu huso", lifecycle.local_now(-4).utcoffset() == timedelta(hours=-4))

# ---- latido de salud
check("sin archivo: no hay latido", lifecycle.alive_age(tmp / "nada") is None)
lifecycle.touch()
check("tras tocar, la edad es casi 0", lifecycle.alive_age() < 5)
old = time.time() - 600
os.utime(lifecycle.ALIVE_FILE, (old, old))
check("un latido viejo se nota", 590 < lifecycle.alive_age() < 700)
lifecycle.touch()


def hc():
    return subprocess.run([sys.executable, "healthcheck.py"], env={**os.environ}, capture_output=True).returncode


check("healthcheck sano = 0", hc() == 0)
os.utime(lifecycle.ALIVE_FILE, (old, old))
check("healthcheck con latido de hace 10 min = 1 (unhealthy)", hc() == 1)
lifecycle.ALIVE_FILE.unlink()
check("healthcheck sin archivo = 1", hc() == 1)

t = lifecycle.start_watchdog(every=0.05)
time.sleep(0.2)
check("el hilo vigía escribe el latido", lifecycle.alive_age() < 2 and t.daemon)
lifecycle._stop.set()
lifecycle._stop.clear()

# ---- daily_restart_due usa la hora, el tiempo encendido y la seguridad de la base
class DB:
    def __init__(self, safe=True, boom=False):
        self.safe, self.boom = safe, boom

    def restart_is_safe(self):
        if self.boom:
            raise RuntimeError("sin red")
        return self.safe


real_local, real_started, real_hour = lifecycle.local_now, lifecycle.STARTED, config.RESTART_HOUR
lifecycle.local_now = lambda tz_offset=None: at(4)
lifecycle.STARTED = time.time() - 25 * H
config.RESTART_HOUR = 4
check("toca reiniciar y es seguro", lifecycle.daily_restart_due(DB(True)))
check("hay publicaciones cerca: no", not lifecycle.daily_restart_due(DB(False)))
check("si no se puede saber si es seguro: no", not lifecycle.daily_restart_due(DB(boom=True)))
config.RESTART_HOUR = -1
check("apagado por config", not lifecycle.daily_restart_due(DB(True)))
config.RESTART_HOUR = 4
lifecycle.STARTED = time.time() - 60
check("recién arrancado no reinicia", not lifecycle.daily_restart_due(DB(True)))
lifecycle.local_now, lifecycle.STARTED, config.RESTART_HOUR = real_local, real_started, real_hour

try:
    lifecycle.main_exit("prueba")
    check("main_exit sale", False)
except SystemExit as e:
    check("main_exit sale con código 0 (Docker lo levanta de nuevo)", e.code == 0)
lifecycle._stop.clear()

# ---- apagado ordenado
import signal  # noqa: E402

lifecycle.install_signals()
check("SIGTERM tiene manejador (como PID 1 si no, Docker espera 10 s y corta)", signal.getsignal(signal.SIGTERM) not in (signal.SIG_DFL, signal.SIG_IGN))
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.signal(signal.SIGINT, signal.default_int_handler)

# ---- base: recuperación al arrancar y seguridad del reinicio (con Supabase simulado)
class Q:
    def __init__(self, sb, table):
        self.sb, self.t, self.f, self.upd, self.cnt = sb, table, [], None, False

    def select(self, *a, count=None, **k):
        self.cnt = bool(count)
        return self

    def update(self, v):
        self.upd = v
        return self

    def _flt(self, k, v, op):
        self.f.append((k, v, op))
        return self

    def eq(self, k, v):
        return self._flt(k, v, "eq")

    def in_(self, k, v):
        return self._flt(k, v, "in")

    def lte(self, k, v):
        return self._flt(k, v, "lte")

    def execute(self):
        rows = [r for r in self.sb.tables[self.t] if all(
            (r.get(k) == v if o == "eq" else r.get(k) in v if o == "in" else str(r.get(k)) <= str(v)) for k, v, o in self.f)]
        if self.upd is not None:
            for r in rows:
                r.update(self.upd)
            return types.SimpleNamespace(data=rows, count=len(rows))
        return types.SimpleNamespace(data=rows, count=len(rows))


class FakeSB:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return Q(self, name)


fake_supabase = types.ModuleType("supabase")
fake_supabase.create_client = lambda *a, **k: FakeSB({})
sys.modules["supabase"] = fake_supabase
import db  # noqa: E402

future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
soon = (datetime.now(timezone.utc) + timedelta(minutes=3)).isoformat()
jobs = [{"id": "a", "type": "download", "status": "running", "attempts": 1, "source_id": "s1"},
        {"id": "b", "type": "clip", "status": "running", "attempts": 1, "source_id": "s2"},
        {"id": "c", "type": "record", "status": "running", "attempts": 1, "source_id": "s3"},
        {"id": "d", "type": "download", "status": "running", "attempts": 99, "source_id": "s4"},
        {"id": "e", "type": "download", "status": "queued", "attempts": 0, "source_id": "s5"}]
db.sb = FakeSB({"jobs": jobs, "sources": [{"id": "s4", "status": "x"}], "posts": [], "clips": []})
db.finish_job = lambda jid, ok=True, error=None: next(j for j in jobs if j["id"] == jid).update(status="error" if not ok else "done")
db.set_source = lambda *a, **k: None
n = db.recover_on_start()
st = {j["id"]: j["status"] for j in jobs}
check("los trabajos a medias vuelven a la cola", st["a"] == "queued" and st["b"] == "queued" and n == 2)
check("un directo que se cortó NO se retoma", st["c"] == "running")
check("el que ya falló varias veces va a error, no en bucle", st["d"] == "error")
check("lo que ya estaba en cola no se toca", st["e"] == "queued")

db.live_active = lambda: False
db.sb = FakeSB({"posts": [{"status": "queued", "scheduled_at": future}], "clips": []})
check("sin nada cercano, reiniciar es seguro", db.restart_is_safe() is True)
db.sb = FakeSB({"posts": [{"status": "publishing", "scheduled_at": future}], "clips": []})
check("publicando ahora: no es seguro", db.restart_is_safe() is False)
db.sb = FakeSB({"posts": [{"status": "queued", "scheduled_at": soon}], "clips": []})
check("publicación en 3 min: no es seguro", db.restart_is_safe() is False)
db.sb = FakeSB({"posts": [], "clips": [{"publish_status": "scheduled", "scheduled_at": soon}]})
check("clip programado a mano en 3 min: no es seguro", db.restart_is_safe() is False)
db.sb = FakeSB({"posts": [], "clips": []})
db.live_active = lambda: True
check("grabando un directo: no es seguro", db.restart_is_safe() is False)

# ---- archivos de Docker
root = Path(__file__).parent
compose = (root / "docker-compose.yml").read_text()
check("compose: se levanta solo", "restart: unless-stopped" in compose and "env_file: .env" in compose)
check("compose: guarda trabajo, logs y modelo", "./work:/app/work" in compose and "./logs:/app/logs" in compose and "hf_cache" in compose)
dock = (root / "Dockerfile").read_text()
check("Dockerfile: healthcheck y entrypoint", "HEALTHCHECK" in dock and "healthcheck.py" in dock and "docker-entrypoint.sh" in dock)
ent = (root / "docker-entrypoint.sh").read_text()
check("entrypoint: actualiza yt-dlp sin tumbar el arranque", "pip install" in ent and "exec python" in ent and "\r" not in ent)
check("los .bat tienen saltos de Windows", all(b"\r\n" in (root / f).read_bytes() for f in ("INICIAR-SIEMPRE.bat", "DETENER-WORKER.bat", "VER-LOGS.bat")))
check("logs no entran a la imagen", "logs/" in (root / ".dockerignore").read_text())

print(f"OK: {ok} comprobaciones")
