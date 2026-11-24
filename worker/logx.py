"""Logs claros sin tocar los cientos de print() que ya hay: cada línea sale con hora y con la etiqueta del trabajo
y además se guarda en logs/worker.log (se rota solo). Uso: logx.install() una vez al arrancar; logx.job(id, tipo) por trabajo."""
import contextlib
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
import logging

import config

_tag = threading.local()
_installed = False
_file_logger = None


def _stamp() -> str:
    return time.strftime("%H:%M:%S")


class _Tee:
    """Reemplaza sys.stdout: antepone hora + etiqueta del trabajo a cada línea y copia al archivo."""

    def __init__(self, real):
        self.real = real
        self._buf = ""

    def write(self, text):
        if not text:
            return 0
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._emit(line)
        return len(text)

    def _emit(self, line):
        if not line.strip():
            self.real.write("\n")
            return
        tag = getattr(_tag, "v", "")
        out = f"{_stamp()} {('[' + tag + '] ') if tag else ''}{line}"
        try:
            self.real.write(out + "\n")
        except UnicodeEncodeError:   # consolas de Windows sin UTF-8
            self.real.write(out.encode("ascii", "replace").decode() + "\n")
        if _file_logger:
            _file_logger.info(out)

    def flush(self):
        self.real.flush()

    def isatty(self):
        return getattr(self.real, "isatty", lambda: False)()

    def __getattr__(self, name):
        return getattr(self.real, name)


def install():
    """Activa la hora, las etiquetas y el archivo de log. Si no se puede escribir el archivo, sigue solo en pantalla."""
    global _installed, _file_logger
    if _installed:
        return
    _installed = True
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(config.LOG_DIR / "worker.log", maxBytes=config.LOG_MAX_MB * 1024 * 1024,
                                backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(message)s"))
        _file_logger = logging.getLogger("clipforge.worker")
        _file_logger.setLevel(logging.INFO)
        _file_logger.propagate = False
        _file_logger.addHandler(h)
    except OSError:
        _file_logger = None
    sys.stdout = _Tee(sys.stdout)


def set_tag(tag: str = ""):
    _tag.v = tag


@contextlib.contextmanager
def job(job_id, jtype="", source_id=None):
    """Todo lo que se imprima dentro sale con [tipo id]. Al terminar imprime cuánto tardó."""
    short = str(job_id)[:6]
    label = f"{jtype} {short}".strip()
    set_tag(label)
    t0 = time.time()
    try:
        yield
    finally:
        print(f"Fin del trabajo ({fmt_dur(time.time() - t0)})", flush=True)
        set_tag("")


def fmt_dur(sec: float) -> str:
    sec = int(round(sec))
    if sec < 60:
        return f"{sec} s"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} min {s:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"


class Stages:
    """Cronómetro por etapa: st.begin('descarga') ... st.summary() -> 'descarga 40 s · transcripción 2 min 10 s'."""

    def __init__(self):
        self.items, self._cur, self._t = [], None, 0.0

    def begin(self, name):
        self.end()
        self._cur, self._t = name, time.time()
        print(f"▶ {name}", flush=True)

    def end(self):
        if self._cur:
            self.items.append((self._cur, time.time() - self._t))
            self._cur = None

    def summary(self):
        self.end()
        return " · ".join(f"{n} {fmt_dur(d)}" for n, d in self.items)
