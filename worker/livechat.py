"""Chat en vivo de un directo (YouTube y Twitch) como pista de viralidad.

Lee el chat en un hilo aparte con `chat-downloader` y guarda la hora de cada mensaje. Con eso se calcula en qué segundos
de la grabación el chat explotó (se marcan como 💬). Todo es opcional: si la librería no está o el chat falla,
el directo sigue igual, solo sin esta pista.
"""
import threading
import time

import energy

MAX_MESSAGES = 300_000


def _to_epoch(ts):
    """chat-downloader da la hora en microsegundos (a veces ms o s). Devuelve segundos desde 1970 o None."""
    try:
        t = float(ts)
    except (TypeError, ValueError):
        return None
    if t > 1e14:
        return t / 1e6
    if t > 1e11:
        return t / 1e3
    return t if t > 1e9 else None


class LiveChat:
    def __init__(self, url, log=print):
        self.url = url
        self.log = log
        self._wall = []            # hora real (epoch) de cada mensaje
        self._sessions = []        # [{w0, t0, w1}]: cada vez que arranca ffmpeg (para pasar hora real -> línea de tiempo)
        self._stop = threading.Event()
        self._thread = None
        self.error = None
        self.started = False

    # ---- sesiones de grabación: relacionan la hora real con el segundo de la grabación
    def session_start(self, timeline_sec, wall=None):
        self._sessions.append({"w0": wall if wall is not None else time.time(), "t0": float(timeline_sec), "w1": None})

    def session_end(self, wall=None):
        if self._sessions and self._sessions[-1]["w1"] is None:
            self._sessions[-1]["w1"] = wall if wall is not None else time.time()

    def timeline_times(self):
        """Segundos de la línea de tiempo de la grabación en que llegó cada mensaje (descarta los de los huecos)."""
        out = []
        sessions = list(self._sessions)
        for w in list(self._wall):
            for s in reversed(sessions):
                if w >= s["w0"]:
                    if s["w1"] is None or w <= s["w1"]:
                        out.append(s["t0"] + (w - s["w0"]))
                    break
        return out

    def count(self):
        return len(self._wall)

    def hot(self, lo, hi, **kw):
        return energy.hot_from_times(self.timeline_times(), lo, hi, **kw)

    # ---- lectura del chat
    def add(self, ts=None):
        """Registra un mensaje (hora real). Público para poder probarlo sin internet."""
        if len(self._wall) < MAX_MESSAGES:
            self._wall.append(_to_epoch(ts) or time.time())

    def start(self):
        if self._thread:
            return
        try:
            import chat_downloader  # noqa: F401
        except ImportError:
            self.error = "falta chat-downloader (pip install chat-downloader)"
            self.log(f"  Chat en vivo: {self.error}. Sigo sin esa pista.")
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="livechat")
        self._thread.start()

    def _run(self):
        from chat_downloader import ChatDownloader
        fails = 0
        while not self._stop.is_set() and fails < 5:
            chat = None
            try:
                chat = ChatDownloader().get_chat(self.url, message_types=["text_message"])
                if not self.started:
                    self.started = True
                    self.log("  Chat en vivo: conectado, leyendo mensajes.")
                fails = 0
                for msg in chat:
                    if self._stop.is_set():
                        break
                    self.add(msg.get("timestamp"))
                if self._stop.is_set():
                    break
                time.sleep(5)       # el chat se cerró solo (directo terminado o corte): se reintenta unas veces
                fails += 1
            except Exception as e:  # noqa: BLE001
                fails += 1
                self.error = f"{type(e).__name__}: {str(e)[:100]}"
                if fails == 1:
                    self.log(f"  Chat en vivo: no pude leerlo ({self.error}); reintento.")
                self._stop.wait(10 * fails)
            finally:
                close = getattr(chat, "close", None)
                if callable(close):
                    try:
                        close()
                    except Exception:  # noqa: BLE001
                        pass

    def stop(self):
        self._stop.set()
