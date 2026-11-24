"""Buscador TikTok/Reels: lógica pura y encolado, sin red."""
import time

import config
import search

ok = 0


def check(name, cond):
    global ok
    assert cond, name
    ok += 1


TT = "https://www.tiktok.com/@khaby.lame"
TTV = "https://www.tiktok.com/@khaby.lame/video/7709194461913419038"
IG = "https://www.instagram.com/explore/tags/viral/"
IGR = "https://www.instagram.com/reel/C1abcXYZ/"

# --- reconocimiento de redes y de link concreto vs perfil
check("red TikTok", search.network_of(TT) == "tiktok")
check("red Instagram", search.network_of(IGR) == "instagram")
check("video TikTok", search.is_video_url(TTV))
check("perfil TikTok no es video", not search.is_video_url(TT))
check("reel Instagram", search.is_video_url(IGR))
check("hashtag Instagram no es video", not search.is_video_url(IG))

# --- texto libre -> links
targets = search.parse_targets("@khaby.lame, #viral https://www.tiktok.com/@user/video/123")
check("parsea @usuario", targets[0] == "https://www.tiktok.com/@khaby.lame")
check("parsea #hashtag", "instagram.com/explore/tags/viral" in targets[1])
check("parsea link directo", targets[2].startswith("https://www.tiktok.com/@user/video/"))

# --- puntaje: un video viral reciente gana, uno viejo/poco visto se descarta
now = time.time()
viral = {"view_count": 2_000_000, "like_count": 150_000, "comment_count": 3000,
         "duration": 27, "timestamp": now - 6 * 3600}
ok_v, _, score, speed = search.evaluate(viral, {})
check("video viral sirve", ok_v and score >= 70 and speed > 100000)
low = {**viral, "view_count": 900, "like_count": 20}
check("pocas vistas se descarta", not search.evaluate(low, {})[0])
old = {**viral, "timestamp": now - 200 * 3600}
check("video viejo se descarta", not search.evaluate(old, {})[0])
flat = {**viral, "like_count": 20}
check("sin interacción se descarta", not search.evaluate(flat, {})[0])
check("opciones de la búsqueda mandan", not search.evaluate(viral, {"min_views": 5_000_000})[0])
# el candidato normalizado usa claves cortas (views/likes/comments)
norm = {"views": viral["view_count"], "likes": viral["like_count"], "comments": viral["comment_count"],
        "duration": viral["duration"], "timestamp": viral["timestamp"]}
check("candidato normalizado se puntúa igual", search.evaluate(norm, {})[0])

# --- marca
check("título publicitario se marca", search.branded_by_text("SPONSORED por marca"))
check("clip normal no se marca", not search.branded_by_text("Lo que dijo en la cena"))

# --- recolección con yt-dlp falso: perfiles y links, sin duplicar
real_extract = search._extract
try:
    search._extract = lambda url, flat=True, playlistend=20: {
        "id": "abc1234567890", "entries": [
            {"id": "v1", "title": "Uno", "url": TTV, "view_count": 10, "duration": 12},
            {"id": "v1", "title": "Repetido", "url": TTV},
            {"id": "v2", "title": "Dos", "url": "https://www.tiktok.com/@x/video/2"},
        ]} if flat else {"id": "v1", "title": "Uno", "view_count": 10, "url": TTV}
    found = search.collect([TT, TT], [], 5, log=lambda *_: None)
    check("perfil devuelve candidatos", len(found) == 2)
    check("dedupe por video", len({c["video_id"] for c in found}) == 2)
    check("link directo también se lee", len(search.collect([], [TTV], 5, log=lambda *_: None)) == 1)
finally:
    search._extract = real_extract

print(f"OK: {ok} comprobaciones del buscador")
