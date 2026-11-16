"""Mi página: lee los números de lo que publicas (vistas, likes, comentarios) y aprende tus mejores horas con datos reales.

  score(s)                       -> puntaje de una publicación (vistas + 3 likes + 8 comentarios + 10 compartidos)
  learn(items, ...)              -> {red: {enough, have, need, slots, rows}}   lógica pura, con pruebas
  due_for_refresh(items, stats)  -> cuáles publicaciones conviene volver a leer (lógica pura)
  fetch_facebook / fetch_instagram / fetch_youtube   leen la Graph API y la API de YouTube
  tick(db)                       -> una vuelta: lee números, guarda seguidores y recalcula las horas

Cómo se aprenden las horas: se agrupan tus publicaciones (con 24 h o más) por hora del día, se compara cada una contra el promedio
de SU red (así Facebook y YouTube se pueden mezclar) y se eligen las horas que rinden más, separadas entre sí. Una hora con
pocas publicaciones se acerca al promedio para que un golpe de suerte no la haga ganar. Una de las horas es de PRUEBA (un horario
poco probado), para que el sistema siga descubriendo y no se quede atrapado en lo que ya hace.
Con menos de LEARN_MIN_POSTS publicaciones no cambia nada: se siguen usando POST_SLOTS.
"""
import statistics
import time
from datetime import datetime, timedelta, timezone

import requests

import config

API = "https://graph.facebook.com/v21.0"
YT_API = "https://www.googleapis.com/youtube/v3"
NETS = ("facebook", "instagram", "youtube")

_last = 0.0
_last_learn = 0.0
_last_followers = 0.0


# ----------------------------------------------------------------------------- lógica pura
def score(s):
    return (int(s.get("views") or 0) + 3 * int(s.get("likes") or 0)
            + 8 * int(s.get("comments") or 0) + 10 * int(s.get("shares") or 0))


def _dt(v):
    if isinstance(v, datetime):
        d = v
    else:
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _circ(a, b):
    d = abs(a - b) % 24
    return min(d, 24 - d)


def _label(minutes):
    m = int(round(minutes / 15.0) * 15) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def _hour_of(slot):
    return int(slot.split(":")[0])


def _defaults(defaults):
    out = []
    for s in defaults or config.POST_SLOTS:
        try:
            h, m = s.split(":")
            out.append(f"{int(h):02d}:{int(m):02d}")
        except ValueError:
            continue
    return out


def learn_one(items, now, tz, n, min_posts, min_per_hour, gap_h, explore, defaults, min_age_h=24):
    """items = publicaciones de UNA red (o todas, ya normalizadas con 'norm'). Devuelve {enough, have, need, slots, rows}."""
    mature = [i for i in items if i.get("when") and (now - i["when"]).total_seconds() >= min_age_h * 3600]
    out = {"enough": False, "have": len(mature), "need": min_posts, "slots": sorted(defaults[:n]), "rows": []}
    if len(mature) < min_posts:
        return out
    buckets = {}
    for i in mature:
        loc = i["when"].astimezone(tz)
        buckets.setdefault(loc.hour, []).append((i["norm"], loc.hour * 60 + loc.minute))
    g = sum(i["norm"] for i in mature) / len(mature)
    if g <= 0:
        return out      # nadie vio nada todavía: no hay nada que aprender
    k = 2.0             # cada hora "vale" k publicaciones promedio de entrada: con pocas, se acerca al promedio
    rows = {}
    for h, vals in buckets.items():
        norms = [v[0] for v in vals]
        shrunk = (sum(norms) + k * g) / (len(norms) + k)
        slot = _label(statistics.median(v[1] for v in vals))
        rows[slot] = {"slot": slot, "score": round(shrunk / g, 3), "posts": len(vals), "chosen": False, "explore": False, "_h": h}
    cands = sorted((r for r in rows.values() if r["posts"] >= min_per_hour), key=lambda r: (-r["score"], -r["posts"]))
    top_n = max(1, n - 1) if explore and n > 1 else n
    chosen = []
    for r in cands:
        if len(chosen) >= top_n:
            break
        if all(_circ(r["_h"], c["_h"]) >= gap_h for c in chosen):
            r["chosen"] = True
            chosen.append(r)
    if explore and n > 1 and len(chosen) < n:
        # hora de prueba: la menos probada entre las de día (10-22 h) que no choque con las elegidas
        opts = [h for h in range(10, 23) if all(_circ(h, c["_h"]) >= gap_h for c in chosen)]
        if opts:
            posts_in = lambda h: len(buckets.get(h, []))  # noqa: E731
            h = min(opts, key=lambda h: (posts_in(h), abs(h - 19)))
            slot = next((s for s, r in rows.items() if r["_h"] == h), f"{h:02d}:00")
            r = rows.setdefault(slot, {"slot": slot, "score": 0.0, "posts": posts_in(h), "chosen": False, "explore": False, "_h": h})
            r["chosen"], r["explore"] = True, True
            chosen.append(r)
    for d in _defaults(defaults):     # si faltan horas (pocos datos por hora), se completa con las de siempre
        if len(chosen) >= n:
            break
        h = _hour_of(d)
        if all(_circ(h, c["_h"]) >= gap_h for c in chosen):
            r = rows.setdefault(d, {"slot": d, "score": 0.0, "posts": len(buckets.get(h, [])), "chosen": False, "explore": False, "_h": h})
            r["chosen"] = True
            chosen.append(r)
    out["enough"] = True
    out["slots"] = sorted(r["slot"] for r in chosen)
    out["rows"] = [{k2: v for k2, v in r.items() if k2 != "_h"} for r in sorted(rows.values(), key=lambda r: r["slot"])]
    return out


def learn(items, now=None, tz=None, n=None, min_posts=None, min_per_hour=None, gap_h=None, explore=None, defaults=None):
    """items = [{network, published_at, views, likes, comments, shares}] -> {'all': {...}, 'facebook': {...}, ...}.
    Cada red se compara con su propio promedio; 'all' junta las redes para cuando una sola no tiene suficientes datos."""
    now = now or datetime.now(timezone.utc)
    tz = tz or timezone(timedelta(hours=config.POST_TZ_OFFSET))
    n = n or config.LEARN_SLOT_COUNT
    min_posts = config.LEARN_MIN_POSTS if min_posts is None else min_posts
    min_per_hour = config.LEARN_MIN_PER_HOUR if min_per_hour is None else min_per_hour
    gap_h = config.LEARN_GAP_HOURS if gap_h is None else gap_h
    explore = config.LEARN_EXPLORE if explore is None else explore
    defaults = defaults or _defaults(None)
    rows = []
    for i in items:
        when = _dt(i.get("published_at"))
        if when:
            rows.append({**i, "when": when, "raw": score(i)})
    base = {}
    for net in NETS:
        vals = [r["raw"] for r in rows if r["network"] == net]
        pos = [v for v in vals if v > 0]
        base[net] = (statistics.median(pos) if pos else 0) or 0
    for r in rows:
        b = base.get(r["network"]) or 0
        r["norm"] = (r["raw"] / b) if b else 0.0
    res = {"all": learn_one(rows, now, tz, n, min_posts, min_per_hour, gap_h, explore, defaults)}
    for net in NETS:
        sub = [r for r in rows if r["network"] == net]
        if sub:
            res[net] = learn_one(sub, now, tz, n, min_posts, min_per_hour, gap_h, explore, defaults)
    return res


def due_for_refresh(items, stats, now=None, minutes=None, batch=None):
    """items = [{network, external_id, published_at}], stats = {(red, id): {fetched_at}}.
    Lo recién publicado se vuelve a leer seguido; lo de más de 3 días, cada 12 h. Primero lo que nunca se leyó."""
    now = now or datetime.now(timezone.utc)
    minutes = config.STATS_MINUTES if minutes is None else minutes
    batch = config.STATS_BATCH if batch is None else batch
    due = []
    for it in items:
        when = _dt(it.get("published_at")) or now
        st = stats.get((it["network"], str(it["external_id"])))
        if not st:
            due.append((0, when, it))
            continue
        fetched = _dt(st.get("fetched_at"))
        every = timedelta(minutes=minutes) if (now - when) < timedelta(days=3) else timedelta(hours=max(12, minutes / 60))
        if not fetched or now - fetched >= every:
            due.append((1, fetched or when, it))
    due.sort(key=lambda x: (x[0], x[1]))
    return [it for _, _, it in due[:batch]]


# ----------------------------------------------------------------------------- lectura de las redes
def _json(r):
    try:
        return r.json()
    except ValueError:
        return {}


def fetch_facebook(video_id, get=None):
    """{views, likes, comments, shares} de un Reel/video de tu página. Lanza RuntimeError si no se pudo leer."""
    get = get or requests.get
    tok = config.FB_PAGE_TOKEN
    fields = "views,likes.summary(true).limit(0),comments.summary(true).limit(0)"
    r = get(f"{API}/{video_id}", params={"fields": fields, "access_token": tok}, timeout=30)
    if not r.ok:    # algunas versiones no dan "views": se pide sin él y se lee aparte
        r = get(f"{API}/{video_id}", params={"fields": "likes.summary(true).limit(0),comments.summary(true).limit(0)", "access_token": tok}, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Facebook no dio los números ({_json(r).get('error', {}).get('message', r.text[:120])})")
    j = _json(r)
    views = j.get("views")
    if views is None:
        ins = get(f"{API}/{video_id}/video_insights", params={"metric": "total_video_views", "access_token": tok}, timeout=30)
        try:
            views = ins.json()["data"][0]["values"][0]["value"] if ins.ok else 0
        except (KeyError, IndexError, ValueError, TypeError):
            views = 0
    cnt = lambda k: int(((j.get(k) or {}).get("summary") or {}).get("total_count") or 0)  # noqa: E731
    return {"views": int(views or 0), "likes": cnt("likes"), "comments": cnt("comments"), "shares": 0}


def fetch_instagram(media_id, get=None):
    get = get or requests.get
    tok = config.IG_TOKEN
    r = get(f"{API}/{media_id}", params={"fields": "like_count,comments_count", "access_token": tok}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"Instagram no dio los números ({_json(r).get('error', {}).get('message', r.text[:120])})")
    j = _json(r)
    out = {"views": 0, "likes": int(j.get("like_count") or 0), "comments": int(j.get("comments_count") or 0), "shares": 0}
    for metric in ("views,shares", "plays,shares", "views"):    # el nombre de la métrica cambia según la versión
        ins = get(f"{API}/{media_id}/insights", params={"metric": metric, "access_token": tok}, timeout=30)
        if not ins.ok:
            continue
        for m in _json(ins).get("data") or []:
            try:
                v = int(m["values"][0]["value"])
            except (KeyError, IndexError, ValueError, TypeError):
                continue
            if m.get("name") in ("views", "plays"):
                out["views"] = v
            elif m.get("name") == "shares":
                out["shares"] = v
        break
    return out


def fetch_youtube(video_ids, get=None):
    """{id: {views, likes, comments, shares}} para hasta 50 videos. Con YT_API_KEY no hace falta permiso de lectura de OAuth."""
    get = get or requests.get
    params, headers = {"part": "statistics", "id": ",".join(video_ids[:50])}, {}
    if config.YT_API_KEY:
        params["key"] = config.YT_API_KEY
    else:
        import publisher_yt
        headers["Authorization"] = f"Bearer {publisher_yt.access_token()}"
    r = get(f"{YT_API}/videos", params=params, headers=headers, timeout=30)
    if not r.ok:
        why = _json(r).get("error", {}).get("message", r.text[:120])
        raise RuntimeError(f"YouTube no dio los números ({why}). Pon YT_API_KEY en .env o autoriza el permiso youtube.readonly")
    out = {}
    for it in _json(r).get("items") or []:
        st = it.get("statistics") or {}
        out[it["id"]] = {"views": int(st.get("viewCount") or 0), "likes": int(st.get("likeCount") or 0),
                         "comments": int(st.get("commentCount") or 0), "shares": 0}
    return out


def fetch_followers(network, get=None):
    """Seguidores ahora mismo, o None si no se pudo."""
    get = get or requests.get
    try:
        if network == "facebook":
            r = get(f"{API}/{config.FB_PAGE_ID}", params={"fields": "followers_count,fan_count", "access_token": config.FB_PAGE_TOKEN}, timeout=30)
            j = _json(r)
            return int(j.get("followers_count") or j.get("fan_count")) if r.ok and (j.get("followers_count") or j.get("fan_count")) else None
        if network == "instagram":
            r = get(f"{API}/{config.IG_USER_ID}", params={"fields": "followers_count", "access_token": config.IG_TOKEN}, timeout=30)
            return int(_json(r)["followers_count"]) if r.ok and "followers_count" in _json(r) else None
        if network == "youtube":
            params, headers = {"part": "statistics", "mine": "true"}, {}
            import publisher_yt
            headers["Authorization"] = f"Bearer {publisher_yt.access_token()}"
            r = get(f"{YT_API}/channels", params=params, headers=headers, timeout=30)
            items = _json(r).get("items") or []
            return int(items[0]["statistics"]["subscriberCount"]) if r.ok and items else None
    except Exception:  # noqa: BLE001  (los seguidores son un extra)
        return None
    return None


def configured(network):
    if network == "facebook":
        return bool(config.FB_PAGE_ID and config.FB_PAGE_TOKEN)
    if network == "instagram":
        import publisher_ig
        return publisher_ig.configured()
    if network == "youtube":
        import publisher_yt
        return publisher_yt.configured() or bool(config.YT_API_KEY)
    return False


# ----------------------------------------------------------------------------- vuelta del worker
def refresh(db, now=None, fetchers=None):
    """Lee los números de las publicaciones que toca. Devuelve cuántas guardó."""
    now = now or datetime.now(timezone.utc)
    f = {"facebook": fetch_facebook, "instagram": fetch_instagram, "youtube": fetch_youtube, **(fetchers or {})}
    items = [i for i in db.published_items(config.STATS_DAYS) if (fetchers or configured(i["network"]))]
    stats = db.stats_map()
    todo = due_for_refresh(items, stats, now)
    saved = []
    yt = [i for i in todo if i["network"] == "youtube"]
    for it in todo:
        if it["network"] == "youtube":
            continue
        row = {"network": it["network"], "external_id": str(it["external_id"]), "post_id": it.get("post_id"), "clip_id": it.get("clip_id"),
               "published_at": it.get("published_at"), "fetched_at": now.isoformat()}
        try:
            row.update(f[it["network"]](str(it["external_id"])), error=None)
        except Exception as e:  # noqa: BLE001
            row["error"] = str(e)[:200]
            prev = stats.get((it["network"], str(it["external_id"]))) or {}
            for k in ("views", "likes", "comments", "shares"):
                row[k] = int(prev.get(k) or 0)    # un error no borra lo que ya se sabía
        saved.append(row)
    if yt:
        try:
            got = f["youtube"]([str(i["external_id"]) for i in yt])
            err = None
        except Exception as e:  # noqa: BLE001
            got, err = {}, str(e)[:200]
        for it in yt:
            prev = stats.get(("youtube", str(it["external_id"]))) or {}
            base = {k: int(prev.get(k) or 0) for k in ("views", "likes", "comments", "shares")}
            cur = got.get(str(it["external_id"]))
            saved.append({"network": "youtube", "external_id": str(it["external_id"]), "post_id": it.get("post_id"), "clip_id": it.get("clip_id"),
                          "published_at": it.get("published_at"), "fetched_at": now.isoformat(), **(cur or base),
                          "error": (err or "YouTube no devolvió este video (¿privado o borrado?)") if cur is None else None})
    if saved:
        db.save_stats(saved)
    return len(saved)


def relearn(db, now=None):
    """Recalcula las mejores horas con lo que hay guardado y las guarda. Devuelve {red: horas}."""
    items = db.stats_for_learning(max(config.STATS_DAYS, 60))
    res = learn(items, now)
    for net, r in res.items():
        db.save_best_hours(net, r["rows"] if r["enough"] else [])
    return {n: r["slots"] for n, r in res.items() if r["enough"]}


def tick(db=None):
    """Llamar desde el hilo de publicación. Lee números cada rato, guarda seguidores 1 vez al día y recalcula horas."""
    global _last, _last_learn, _last_followers
    if not config.STATS or time.time() - _last < 300:
        return 0
    _last = time.time()
    if db is None:
        import db as db
    n = refresh(db)
    if n:
        print(f"  Mi página: leí los números de {n} publicación(es)", flush=True)
    if time.time() - _last_followers > 6 * 3600:
        _last_followers = time.time()
        for net in NETS:
            if configured(net):
                v = fetch_followers(net)
                if v is not None:
                    db.save_followers(net, v)
    if config.LEARN_SLOTS and (n or time.time() - _last_learn > 3600):
        _last_learn = time.time()
        learned = relearn(db)
        if learned:
            print("  Mi página: mejores horas aprendidas → " + " · ".join(f"{k}: {', '.join(v)}" for k, v in sorted(learned.items())), flush=True)
    return n
