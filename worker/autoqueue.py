"""Cola automática: toma clips con veredicto 'listo' (o aprobados por ti) y les pone hora en cada red, los mejores primero.

  plan(clips, taken, networks, now, ...) -> [{clip_id, network, scheduled_at}]   (lógica pura, con pruebas)
  tick(db)                                -> crea las publicaciones en la tabla `posts`

Solo corre con el botón «Cola automática» de la web o con AUTO_QUEUE=1. Nunca programa clips en revisión, flojos o ya publicados.
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


def _enabled(db=None):
    """¿Está encendida la cola automática? Manda el botón de la web (Parte 13); si no se puede leer, el AUTO_QUEUE del .env."""
    try:
        if db is None:
            import db as db
        return bool(db.auto_queue_on()) if hasattr(db, "auto_queue_on") else bool(config.AUTO_QUEUE)
    except Exception:  # noqa: BLE001
        return bool(config.AUTO_QUEUE)


def autopilot_networks(pages):
    """Redes internas que usa el piloto: facebook:<id_página> (una fila por página)."""
    return [f"facebook:{p}" for p in pages if str(p).isdigit()]


def tick(db=None):
    global _last
    if time.time() - _last < 120 or not _enabled(db):
        return 0
    _last = time.time()
    if db is None:
        import db as db
    done = 0

    # Piloto automático: el mismo clip se programa en TODAS las páginas elegidas
    # (varios proyectos, varias páginas por proyecto). La web publica por cada página
    # con su token fresco; aquí solo llenamos la cola.
    try:
        cfg = db.autopilot_config() if hasattr(db, "autopilot_config") else {}
    except Exception:  # noqa: BLE001
        cfg = {}
    pages = list(cfg.get("page_ids") or []) if cfg.get("enabled") else []
    if pages:
        targets = autopilot_networks(pages)
        clips = db.clips_ready_for_autopilot(pages, max(1, int(cfg.get("max_per_run") or 5)),
                                             auto_approve=bool(cfg.get("auto_approve")))
        if clips:
            slots = {}
            try:
                learned = db.learned_slots(["facebook"]) if config.LEARN_SLOTS else {}
            except Exception:  # noqa: BLE001
                learned = {}
            for n in targets:
                slots[n] = (learned or {}).get("facebook")
            rows = plan(clips, db.autopilot_taken(pages), targets, pending=db.autopilot_pending(pages),
                        slots=slots, max_pending=int(cfg.get("max_per_run") or 5))
            if rows:
                db.create_posts(rows)
                done += len(rows)
                print(f"  Piloto: {len(rows)} publicación(es) en {len(set(r['network'] for r in rows))} página(s)", flush=True)

    nets = [n for n in networks_available() if not (pages and n == "facebook")]
    if not nets:
        return done
    clips = db.clips_ready_for_queue(nets, 10)
    if not clips:
        return done
    try:
        learned = db.learned_slots(nets) if config.LEARN_SLOTS else None    # horas aprendidas en Mi página
    except Exception:  # noqa: BLE001  (sin migración 0012: se usan POST_SLOTS)
        learned = None
    rows = plan(clips, db.posts_taken(nets), nets, pending=db.posts_pending(nets), slots=learned)
    if rows:
        db.create_posts(rows)
        done += len(rows)
        print(f"  Cola: {len(rows)} publicación(es) programada(s) en {', '.join(sorted({r['network'] for r in rows}))}", flush=True)
    return done
