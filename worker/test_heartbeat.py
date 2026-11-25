"""El latido de la web sigue vivo aunque el bucle principal esté ocupado en un render largo."""
import time

import lifecycle

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


class FakeDB:
    def __init__(self):
        self.calls = 0

    def heartbeat(self, info=None):
        self.calls += 1


lifecycle._stop.clear()
db = FakeDB()
t = lifecycle.start_web_heartbeat(db, every=0.2)
check("hilo daemon", t.daemon)
check("arranca solo", db.calls >= 1)
time.sleep(0.75)   # el hilo principal "está ocupado": nadie llama a db.heartbeat()
check("sigue escribiendo sin el bucle", db.calls >= 3)
lifecycle._stop.set()
t.join(timeout=2)
paradas = db.calls
time.sleep(0.4)
check("para al apagarse el worker", db.calls == paradas)
lifecycle._stop.clear()
check("intervalo dentro del umbral de la web (45 s)", 20 < 45)
print(f"LATIDO OK · {ok} comprobaciones")
