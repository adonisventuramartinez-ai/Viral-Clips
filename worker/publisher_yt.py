"""Sube un video a YouTube como Short (Data API v3, OAuth con refresh token). Un video vertical de hasta 60 s se trata como Short.
Cuota: cada subida gasta 1600 de las 10 000 unidades diarias por defecto (unas 6 subidas al día).
Importante: los proyectos de Google Cloud SIN auditar suben los videos como PRIVADOS; hay que pasar la auditoría de la API para que salgan públicos."""
import requests

import config

TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def configured():
    return bool(config.YT_CLIENT_ID and config.YT_CLIENT_SECRET and config.YT_REFRESH_TOKEN)


def access_token():
    r = requests.post(TOKEN_URL, data={"client_id": config.YT_CLIENT_ID, "client_secret": config.YT_CLIENT_SECRET,
                                       "refresh_token": config.YT_REFRESH_TOKEN, "grant_type": "refresh_token"}, timeout=30)
    if not r.ok:
        raise RuntimeError(f"YouTube no dio acceso (renueva YT_REFRESH_TOKEN): {r.text[:160]}")
    return r.json()["access_token"]


def publish(data, title, description, tags=None):
    """data = bytes del mp4. Devuelve el id del video."""
    tok = access_token()
    meta = {"snippet": {"title": (title or "Clip")[:100], "description": (description or "")[:4900],
                        "tags": [t.lstrip("#") for t in (tags or [])][:10], "categoryId": "24"},
            "status": {"privacyStatus": config.YT_PRIVACY if config.YT_PRIVACY in ("public", "unlisted", "private") else "public",
                       "selfDeclaredMadeForKids": False}}
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json; charset=UTF-8",
         "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(data))}
    init = requests.post(UPLOAD_URL, params={"uploadType": "resumable", "part": "snippet,status"}, headers=h, json=meta, timeout=60)
    if not init.ok:
        raise RuntimeError(f"YouTube rechazó los datos del video: {init.text[:200]}")
    up = requests.put(init.headers["Location"], data=data, headers={"Content-Type": "video/mp4"}, timeout=900)
    if not up.ok:
        raise RuntimeError(f"YouTube no recibió el archivo: {up.text[:200]}")
    return up.json()["id"]
