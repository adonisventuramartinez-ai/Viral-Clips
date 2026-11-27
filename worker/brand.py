"""Marca y estilo que se aplican a todos los clips: logo, subtítulos y texto gancho.
Se configuran en la web (Ajustes IA) y se guardan en Supabase Storage (bucket 'uploads', carpeta 'brand/').
Si no hay nada guardado, usa el archivo de LOGO_PATH del .env (si existe) y el estilo clásico."""
import json
from pathlib import Path

import config
import db

LOGO_DEFAULTS = {"pos": "bc", "size": 24, "opacity": 100, "margin": 110}
SUB_KEYS = ("text", "active", "outline", "size", "outline_w", "upper", "pop", "offset")


TEMPLATES = "brand/templates.json"   # {"items": {id: {"name": ..., "settings": {...}}}} (lo escribe la web en Ajustes > Marca)


def _read_json(path):
    try:
        raw = db.sb.storage.from_("uploads").download(path)
        return json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:  # noqa: BLE001
        return {}


def pick_settings(template, main_cfg, templates):
    """Configuración a usar: la plantilla pedida (si existe) y si no, la configuración general. Devuelve (cfg, nombre|None)."""
    item = ((templates or {}).get("items") or {}).get(template or "")
    if item and isinstance(item.get("settings"), dict):
        return {**item["settings"]}, item.get("name") or template
    return main_cfg, None


def load(workdir: Path, template=None) -> dict:
    """Siempre devuelve un dict: {path?, pos, size, opacity, margin, subs{}, hook, hook_sec}. 'path' solo si hay logo.
    `template` = id de una plantilla de marca guardada en la web; si no existe se usa la marca general."""
    cfg = _read_json("brand/settings.json")
    tname = None
    if template:
        cfg, tname = pick_settings(template, cfg, _read_json(TEMPLATES))
        print(f"  Plantilla de marca: {tname}" if tname else f"  Plantilla de marca '{template}' no existe: uso la marca general", flush=True)

    out = {**LOGO_DEFAULTS, **{k: cfg[k] for k in LOGO_DEFAULTS if k in cfg}}
    out["subs"] = {k: cfg["subs"][k] for k in SUB_KEYS if isinstance(cfg.get("subs"), dict) and k in cfg["subs"]}
    out["hook"] = bool(cfg.get("hook", True))
    out["hook_sec"] = float(cfg.get("hook_sec", 3.5))
    # Marca de agua (texto): primero la guardada en la web, si no la del .env
    wm = cfg.get("watermark") if isinstance(cfg.get("watermark"), dict) else None
    if wm and wm.get("enabled", True) and wm.get("text"):
        out["watermark"] = {"text": str(wm["text"]), "pos": wm.get("pos", "br"), "size": int(wm.get("size", 18)), "opacity": int(wm.get("opacity", 60)) / 100.0}
    elif config.WATERMARK_TEXT:
        out["watermark"] = {"text": config.WATERMARK_TEXT, "pos": config.WATERMARK_POS, "size": config.WATERMARK_SIZE, "opacity": config.WATERMARK_OPACITY}

    if cfg.get("enabled", True) and cfg.get("file"):
        try:
            data = db.sb.storage.from_("uploads").download(cfg["file"])
            dest = Path(workdir) / ("brand_logo" + Path(cfg["file"]).suffix)
            dest.write_bytes(data)
            out["path"] = str(dest)
            print(f"  Logo: lo pongo en {out['pos']} ({out['size']}% del ancho)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  Logo: no pude bajarlo ({type(e).__name__}); sigo sin logo.", flush=True)
    elif tname is None and cfg.get("enabled", True) is not False and config.LOGO_PATH:   # una plantilla sin logo no usa el del .env
        p = Path(config.LOGO_PATH)
        p = p if p.is_absolute() else Path(__file__).parent / p
        if p.exists():
            out.update({"path": str(p), "pos": "tr", "size": 14, "margin": 60})
    return out
