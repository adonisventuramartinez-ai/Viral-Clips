"""Marca y estilo que se aplican a todos los clips: logo, subtítulos y texto gancho.
Se configuran en la web (Ajustes IA) y se guardan en Supabase Storage (bucket 'uploads', carpeta 'brand/').
Si no hay nada guardado, usa el archivo de LOGO_PATH del .env (si existe) y el estilo clásico."""
import json
from pathlib import Path

import config
import db

LOGO_DEFAULTS = {"pos": "bc", "size": 24, "opacity": 100, "margin": 110}
SUB_KEYS = ("text", "active", "outline", "size", "outline_w", "upper", "pop", "offset")


def load(workdir: Path) -> dict:
    """Siempre devuelve un dict: {path?, pos, size, opacity, margin, subs{}, hook, hook_sec}. 'path' solo si hay logo."""
    try:
        raw = db.sb.storage.from_("uploads").download("brand/settings.json")
        cfg = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:  # noqa: BLE001  (no hay configuración guardada)
        cfg = {}

    out = {**LOGO_DEFAULTS, **{k: cfg[k] for k in LOGO_DEFAULTS if k in cfg}}
    out["subs"] = {k: cfg["subs"][k] for k in SUB_KEYS if isinstance(cfg.get("subs"), dict) and k in cfg["subs"]}
    out["hook"] = bool(cfg.get("hook", True))
    out["hook_sec"] = float(cfg.get("hook_sec", 3.5))

    if cfg.get("enabled", True) and cfg.get("file"):
        try:
            data = db.sb.storage.from_("uploads").download(cfg["file"])
            dest = Path(workdir) / ("brand_logo" + Path(cfg["file"]).suffix)
            dest.write_bytes(data)
            out["path"] = str(dest)
            print(f"  Logo: lo pongo en {out['pos']} ({out['size']}% del ancho)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"  Logo: no pude bajarlo ({type(e).__name__}); sigo sin logo.", flush=True)
    elif cfg.get("enabled", True) is not False and config.LOGO_PATH:
        p = Path(config.LOGO_PATH)
        p = p if p.is_absolute() else Path(__file__).parent / p
        if p.exists():
            out.update({"path": str(p), "pos": "tr", "size": 14, "margin": 60})
    return out
