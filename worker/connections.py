"""Cuentas conectadas desde la web (página "Conectar cuentas"): las llaves guardadas en Supabase pasan a config en caliente,
sin reiniciar el worker (se releen cada ~2 min). Lo que guardes en la web manda sobre worker/.env; lo vacío no pisa nada.

  overlay(rows, environ) -> {ATRIBUTO_DE_CONFIG: valor}    lógica pura, con pruebas
  apply(rows)            -> lo pone en config
"""
import os

import config

# red -> {campo de la web: variable de config}
FIELDS = {
    "facebook": {"page_id": "FB_PAGE_ID", "page_token": "FB_PAGE_TOKEN"},
    "instagram": {"user_id": "IG_USER_ID", "token": "IG_TOKEN"},
    "youtube": {"client_id": "YT_CLIENT_ID", "client_secret": "YT_CLIENT_SECRET", "refresh_token": "YT_REFRESH_TOKEN", "api_key": "YT_API_KEY"},
}


def overlay(rows, environ=None):
    environ = os.environ if environ is None else environ
    out = {}
    for r in rows or []:
        fields, data = FIELDS.get(r.get("network")), r.get("data") or {}
        if not fields:
            continue
        for k, attr in fields.items():
            v = str(data.get(k) or "").strip()
            if v:
                out[attr] = v
    # igual que config.py: Instagram usa el token de la página si no tiene el suyo
    if "IG_TOKEN" not in out and not (environ.get("IG_TOKEN") or "").strip():
        tok = out.get("FB_PAGE_TOKEN") or (environ.get("FB_PAGE_TOKEN") or "").strip()
        if tok:
            out["IG_TOKEN"] = tok
    return out


def apply(rows):
    changes = overlay(rows)
    for attr, v in changes.items():
        setattr(config, attr, v)
    return changes
