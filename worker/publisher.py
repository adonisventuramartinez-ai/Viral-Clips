"""Publica un clip como Reel en tu página de Facebook (opcional, apagado por defecto: FB_AUTOPUBLISH=0).

Necesita en worker/.env: FB_PAGE_ID y FB_PAGE_TOKEN (token de página con permiso de publicar).
Flujo oficial de Reels de la Graph API: iniciar -> subir el archivo -> terminar/publicar.
"""
import time
from pathlib import Path

import requests

import config

API = "https://graph.facebook.com/v21.0"


def publish_reel(path, description):
    """Devuelve el id del video o None si algo falla (nunca tumba el trabajo)."""
    if not (config.FB_PAGE_ID and config.FB_PAGE_TOKEN):
        print("  Facebook: faltan FB_PAGE_ID / FB_PAGE_TOKEN, no publico.", flush=True)
        return None
    try:
        tok, pid = config.FB_PAGE_TOKEN, config.FB_PAGE_ID
        r = requests.post(f"{API}/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=60)
        r.raise_for_status()
        j = r.json()
        vid, url = j["video_id"], j["upload_url"]
        data = Path(path).read_bytes()
        u = requests.post(url, headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(len(data))},
                          data=data, timeout=600)
        u.raise_for_status()
        f = requests.post(f"{API}/{pid}/video_reels",
                          data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                "description": (description or "")[:2000],
                                "access_token": tok}, timeout=120)
        f.raise_for_status()
        print(f"  Facebook: Reel enviado (video {vid})", flush=True)
        time.sleep(2)
        return vid
    except Exception as e:  # noqa: BLE001
        print(f"  Facebook: no pude publicar ({type(e).__name__}: {str(e)[:160]})", flush=True)
        return None
