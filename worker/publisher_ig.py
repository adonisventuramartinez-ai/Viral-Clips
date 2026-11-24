"""Publica un Reel en Instagram (Graph API). Necesita IG_USER_ID y un token (IG_TOKEN o FB_PAGE_TOKEN) con instagram_content_publish.
Flujo oficial: crear contenedor con la URL del video -> esperar a que termine de procesar -> publicar.
Instagram descarga el video desde una URL pública, por eso se usa la URL firmada de Supabase."""
import time

import requests

import config

API = "https://graph.facebook.com/v21.0"


def configured():
    return bool(config.IG_USER_ID and config.IG_TOKEN)


def publish(video_url, caption, wait=300, poll=8, cover_url=None):
    """Devuelve el id del medio publicado. Lanza RuntimeError con el motivo si algo falla.
    cover_url = miniatura elegida en Hacerlo viral (URL pública). Si Instagram no la acepta, se publica igual sin portada propia."""
    tok, uid = config.IG_TOKEN, config.IG_USER_ID
    data = {"media_type": "REELS", "video_url": video_url, "caption": (caption or "")[:2200], "share_to_feed": "true", "access_token": tok}
    r = None
    if cover_url:
        r = requests.post(f"{API}/{uid}/media", data={**data, "cover_url": cover_url}, timeout=60)
        if not r.ok:
            print(f"  Instagram no aceptó la portada ({r.text[:120]}); lo publico sin ella.", flush=True)
            r = None
    if r is None:
        r = requests.post(f"{API}/{uid}/media", data=data, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Instagram rechazó el video: {r.text[:200]}")
    cid = r.json()["id"]
    end = time.time() + wait
    while True:
        s = requests.get(f"{API}/{cid}", params={"fields": "status_code,status", "access_token": tok}, timeout=30).json()
        code = s.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram no pudo procesar el video ({s.get('status', code)})")
        if time.time() > end:
            raise RuntimeError("Instagram tardó demasiado procesando el video")
        time.sleep(poll)
    p = requests.post(f"{API}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    if not p.ok:
        raise RuntimeError(f"Instagram no publicó: {p.text[:200]}")
    return p.json()["id"]
