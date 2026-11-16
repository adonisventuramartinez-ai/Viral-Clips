"""Publica un Reel en Instagram (Graph API). Necesita IG_USER_ID y un token (IG_TOKEN o FB_PAGE_TOKEN) con instagram_content_publish.
Flujo oficial: crear contenedor con la URL del video -> esperar a que termine de procesar -> publicar.
Instagram descarga el video desde una URL pública, por eso se usa la URL firmada de Supabase."""
import time

import requests

import config

API = "https://graph.facebook.com/v21.0"


def configured():
    return bool(config.IG_USER_ID and config.IG_TOKEN)


def publish(video_url, caption, wait=300, poll=8):
    """Devuelve el id del medio publicado. Lanza RuntimeError con el motivo si algo falla."""
    tok, uid = config.IG_TOKEN, config.IG_USER_ID
    r = requests.post(f"{API}/{uid}/media", data={"media_type": "REELS", "video_url": video_url, "caption": (caption or "")[:2200],
                                                   "share_to_feed": "true", "access_token": tok}, timeout=60)
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
