"""Cola automática: toma clips con veredicto 'listo' (o aprobados por ti) y les pone hora en cada red, los mejores primero.

  plan(clips, taken, networks, now, ...) -> [{clip_id, network, scheduled_at}]   (lógica pura, con pruebas)
  tick(db)                                -> crea las publicaciones en la tabla `posts`

Solo corre con AUTO_QUEUE=1. Nunca programa clips en revisión, flojos o ya publicados.
"""
import time
from datetime import datetime, timedelta, timezone

import config
import viral

_last = 0.0


def networks_available():
    """Redes con credenciales completas, filtradas por AUTO_NETWORKS si lo pusiste."""
    import publisher_ig
    import publisher_yt
    have = []
    if config.FB_PAGE_ID and config.FB_PAGE_TOKEN:
        have.append("facebook")
    if publisher_ig.configured():
        have.append("instagram")
    if publisher_yt.configured():
        have.append("youtube")
    return [n for n in have if not config.AUTO_NETWORKS or n in config.AUTO_NETWORKS]


def plan(clips, taken, networks, now=None, pending=None, max_ahead_days=None, max_pending=None, slots=None):
    """clips = [{id, viral:{score}}], taken = {red: [fechas ocupadas]}, pending = {red: cuántas en espera},
    slots = {red: ['12:30', ...]} horas aprendidas en Mi página (si falta una red, usa POST_SLOTS).
    Reparte horas buenas: el clip de más puntaje toma la hora más cercana. Devuelve lista de posts a crear."""
    now = now or datetime.now(timezone.utc)
    ahead = now + timedelta(days=config.QUEUE_MAX_AHEAD_DAYS if max_ahead_days is None else max_ahead_days)
    cap = config.QUEUE_MAX_PENDING if max_pending is None else max_pending
    busy = {n: list(taken.get(n, [])) for n in networks}
    count = {n: int((pending or {}).get(n, 0)) for n in networks}
    out = []
    for c in sorted(clips, key=lambda c: -float(((c.get("viral") or {}).get("score")) or c.get("viral_score") or 0)):
        for n in networks:
            if count[n] >= cap:
                continue
            slot = viral.next_slots(now, busy[n], 1, slots=(slots or {}).get(n) or None)
            if not slot or slot[0] > ahead:
                continue
            busy[n].append(slot[0])
            count[n] += 1
            out.append({"clip_id": c["id"], "network": n, "scheduled_at": slot[0].isoformat()})
    return out


def tick(db=None):
    global _last
    if not config.AUTO_QUEUE or time.time() - _last < 120:
        return 0
    _last = time.time()
    if db is None:
        import db as db
    nets = networks_available()
    if not nets:
        return 0
    clips = db.clips_ready_for_queue(nets, 10)
    if not clips:
        return 0
    try:
        learned = db.learned_slots(nets) if config.LEARN_SLOTS else None    # horas aprendidas en Mi página
    except Exception:  # noqa: BLE001  (sin migración 0012: se usan POST_SLOTS)
        learned = None
    rows = plan(clips, db.posts_taken(nets), nets, pending=db.posts_pending(nets), slots=learned)
    if rows:
        db.create_posts(rows)
        print(f"  Cola: {len(rows)} publicación(es) programada(s) en {', '.join(sorted({r['network'] for r in rows}))}", flush=True)
    return len(rows)
