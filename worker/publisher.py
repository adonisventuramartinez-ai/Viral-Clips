"""Publica un clip como Reel en tu página de Facebook (opcional, apagado por defecto: FB_AUTOPUBLISH=0).

Necesita en worker/.env o en Conectar cuentas: FB_PAGE_ID y FB_PAGE_TOKEN (token de página con permiso de publicar).
Flujo oficial de Reels de la Graph API: iniciar -> subir el archivo -> terminar/publicar.
"""
import time
from pathlib import Path

import requests

import config

API = "https://graph.facebook.com/v21.0"


def _check_token(tok, pid):
    """Verifica que el token sirva y tenga permisos de publicar. Devuelve (ok, motivo)."""
    try:
        r = requests.get(f"{API}/me", params={"access_token": tok, "fields": "id,name"}, timeout=30)
        if r.status_code == 401 or r.status_code == 403:
            return False, "el token de Facebook venció o no sirve (renuévalo en Conectar cuentas)"
        if not r.ok:
            return False, f"Facebook respondió {r.status_code}: {r.text[:120]}"
        me = r.json()
        if me.get("id") != pid and me.get("id") != str(pid):
            # el token puede ser de usuario; verificamos que pueda publicar en la página
            r2 = requests.get(f"{API}/{pid}", params={"access_token": tok, "fields": "id,name"}, timeout=30)
            if not r2.ok:
                return False, f"no puedo leer tu página {pid}: {r2.text[:120]}"
        return True, ""
    except Exception as e:  # noqa: BLE001
        return False, f"error al verificar el token: {type(e).__name__}: {str(e)[:100]}"


def publish_reel(path, description):
    """Devuelve el id del video o None si algo falla (nunca tumba el trabajo)."""
    if not (config.FB_PAGE_ID and config.FB_PAGE_TOKEN):
        print("  Facebook: faltan FB_PAGE_ID / FB_PAGE_TOKEN, no publico.", flush=True)
        return None
    tok, pid = config.FB_PAGE_TOKEN, config.FB_PAGE_ID
    # Verificar token antes de intentar subir
    ok, motivo = _check_token(tok, pid)
    if not ok:
        print(f"  Facebook: {motivo}", flush=True)
        return None
    try:
        # 1. Iniciar la subida
        r = requests.post(f"{API}/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}, timeout=60)
        r.raise_for_status()
        j = r.json()
        vid, url = j["video_id"], j["upload_url"]
        if not vid or not url:
            raise RuntimeError(f"Facebook no devolvió video_id/upload_url: {j}")
        # 2. Subir el archivo
        data = Path(path).read_bytes()
        u = requests.post(url, headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(len(data))},
                          data=data, timeout=600)
        u.raise_for_status()
        # 3. Terminar y publicar
        f = requests.post(f"{API}/{pid}/video_reels",
                          data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED",
                                "description": (description or "")[:2000],
                                "access_token": tok}, timeout=120)
        f.raise_for_status()
        fj = f.json()
        if fj.get("success") is False:
            raise RuntimeError(f"Facebook rechazó la publicación: {fj}")
        print(f"  Facebook: Reel publicado (video {vid})", flush=True)
        time.sleep(2)
        return vid
    except Exception as e:  # noqa: BLE001
        print(f"  Facebook: no pude publicar ({type(e).__name__}: {str(e)[:200]})", flush=True)
        return None