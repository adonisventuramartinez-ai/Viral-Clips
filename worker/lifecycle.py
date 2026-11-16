"""Worker siempre activo (Docker): latido de salud, apagado limpio, reinicio diario y recuperación al arrancar.

  should_restart(...)   lógica pura (con pruebas): ¿toca el reinicio diario?
  start_watchdog()      hilo que marca "sigo vivo" cada 30 s en ALIVE_FILE (lo lee healthcheck.py)
  install_signals()     docker stop / apagar Windows: sale ordenado en vez de ser cortado
  daily_restart_due(db) lo llama el bucle del worker cuando está libre

Un reinicio es seguro y barato: Docker (restart: unless-stopped) vuelve a levantar el worker, y al arrancar baja el yt-dlp más nuevo.
"""
import os
import signal
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

ALIVE_FILE = Path(os.environ.get("ALIVE_FILE", "/tmp/worker.alive"))
STARTED = time.time()
_stop = threading.Event()


def should_restart(uptime_s, now_local, idle, safe, hour, min_uptime_h=20):
    """Reinicio diario: solo si lleva rato encendido, es la hora elegida (hora de tu país), no hay trabajo y nada está por publicarse.
    hour = None o negativo lo apaga."""
    if hour is None or hour < 0:
        return False
    return bool(idle and safe and uptime_s >= min_uptime_h * 3600 and now_local.hour == int(hour))


def local_now(tz_offset=None):
    return datetime.now(timezone(timedelta(hours=config.POST_TZ_OFFSET if tz_offset is None else tz_offset)))


def alive_age(path=None, now=None):
    """Segundos desde el último latido, o None si no existe."""
    p = Path(path or ALIVE_FILE)
    try:
        return (now or time.time()) - p.stat().st_mtime
    except OSError:
        return None


def touch(path=None):
    p = Path(path or ALIVE_FILE)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        os.utime(p, None)
    except OSError:
        pass


def start_watchdog(every=30):
    """Hilo aparte: el latido sigue aunque el worker esté en un render o grabando un directo de horas."""
    def loop():
        while not _stop.is_set():
            touch()
            _stop.wait(every)
    touch()
    t = threading.Thread(target=loop, name="alive", daemon=True)
    t.start()
    return t


def install_signals():
    """docker stop manda SIGTERM. Como PID 1 Python lo ignora si no hay manejador: sin esto Docker espera 10 s y corta a la fuerza."""
    def bye(signum, _frame):
        print(f"Recibí la señal de apagado ({signum}): salgo. Lo que estaba en proceso se retoma al volver a encender.", flush=True)
        _stop.set()
        os._exit(0)
    for s in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(s, bye)
        except (ValueError, OSError):   # no es el hilo principal / sistema sin esa señal
            pass


def daily_restart_due(db):
    """True si el worker debe salir ahora para que Docker lo reinicie (ver should_restart). Llamar solo cuando está libre."""
    if not config.RESTART_HOUR >= 0:
        return False
    if not should_restart(time.time() - STARTED, local_now(), True, True, config.RESTART_HOUR):
        return False
    try:
        return bool(db.restart_is_safe())
    except Exception:  # noqa: BLE001
        return False


def main_exit(reason):
    print(f"Reinicio programado ({reason}). Docker me vuelve a levantar solo.", flush=True)
    _stop.set()
    sys.exit(0)
