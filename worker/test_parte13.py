"""Parte 13: interruptores de la web (Clips automáticos y Cola automática) que mandan sobre el .env. Ejecuta: python test_parte13.py"""
import sys
import types

import autoqueue
import config
import discover

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *a, **k: object())   # sin red ni llaves reales
import db  # noqa: E402


class Q:
    """Supabase simulado: guarda lo que devolvería app_switches (o falla como si faltara la migración)."""
    def __init__(self, rows=None, boom=False):
        self.rows, self.boom, self.reads = rows, boom, 0

    def table(self, name):
        assert name == "app_switches"
        return self

    def __getattr__(self, n):
        return lambda *a, **k: self

    def execute(self):
        self.reads += 1
        if self.boom:
            raise RuntimeError("relation app_switches does not exist")
        return types.SimpleNamespace(data=self.rows)


def use(rows=None, boom=False):
    db.sb = Q(rows, boom)
    db._sw["at"] = 0.0
    return db.sb


# ---- el .env manda mientras no toques el botón
config.DISCOVER, config.AUTO_QUEUE = False, False
use([{"discover": None, "auto_queue": None}])
check("sin tocar el botón y .env apagado: apagado", db.discover_on() is False and db.auto_queue_on() is False)
config.DISCOVER, config.AUTO_QUEUE = True, True
db._sw["at"] = 0.0
check("sin tocar el botón y .env encendido: encendido", db.discover_on() is True and db.auto_queue_on() is True)

# ---- el botón manda sobre el .env, en los dos sentidos
config.DISCOVER, config.AUTO_QUEUE = False, False
use([{"discover": True, "auto_queue": True}])
check("botón encendido gana a .env apagado", db.discover_on() is True and db.auto_queue_on() is True)
config.DISCOVER, config.AUTO_QUEUE = True, True
use([{"discover": False, "auto_queue": False}])
check("botón apagado gana a .env encendido", db.discover_on() is False and db.auto_queue_on() is False)
use([{"discover": True, "auto_queue": False}])
check("cada botón es independiente", db.discover_on() is True and db.auto_queue_on() is False)

# ---- sin migración 0015, o sin fila, o con error: manda el .env y no se rompe nada
config.DISCOVER, config.AUTO_QUEUE = True, False
use(boom=True)
check("sin la tabla: manda el .env", db.discover_on() is True and db.auto_queue_on() is False)
use([])
check("sin fila: manda el .env", db.discover_on() is True and db.auto_queue_on() is False)

# ---- se recuerda 15 s (no golpea Supabase en cada vuelta del worker)
q = use([{"discover": True, "auto_queue": True}])
db.discover_on(); db.auto_queue_on(); db.discover_on()
check("lee Supabase una sola vez en la ventana", q.reads == 1)

# ---- discover.tick y autoqueue.tick obedecen el botón (con la db simulada que traen las pruebas viejas)
class FakeDB:
    def __init__(self, d, a):
        self._d, self._a, self.asked = d, a, 0

    def discover_on(self):
        self.asked += 1
        return self._d

    def auto_queue_on(self):
        return self._a

    def due_feeds(self, minutes):
        self.asked += 100
        return []


config.DISCOVER = True
discover._last = 0
f = FakeDB(False, False)
check("botón apagado: Clips automáticos no revisa nada (aunque el .env diga 1)", discover.tick(f, now=1) == 0 and f.asked == 1)
config.DISCOVER = False
discover._last = 0
f = FakeDB(True, False)
discover.tick(f, now=1)
check("botón encendido: revisa las fuentes (aunque el .env diga 0)", f.asked >= 100)


class QDB:
    created = None

    def __init__(self, on):
        self.on = on

    def auto_queue_on(self):
        return self.on

    def clips_ready_for_queue(self, nets, n):
        return []


config.AUTO_QUEUE = True
autoqueue._last = 0
called = []
orig = autoqueue.networks_available
autoqueue.networks_available = lambda: called.append(1) or []
check("cola con botón apagado: ni mira las redes", autoqueue.tick(QDB(False)) == 0 and not called)
autoqueue._last = 0
autoqueue.tick(QDB(True))
check("cola con botón encendido: sigue su camino", called == [1])
autoqueue.networks_available = orig

# ---- una db rara (sin los métodos nuevos) cae al .env, como en las partes anteriores
config.AUTO_QUEUE = False
autoqueue._last = 0
check("db vieja + .env apagado: apagado", autoqueue._enabled(types.SimpleNamespace()) is False)
config.AUTO_QUEUE = True
check("db vieja + .env encendido: encendido", autoqueue._enabled(types.SimpleNamespace()) is True)

print(f"OK: {ok} comprobaciones")
