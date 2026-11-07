"""Revisa al arrancar que todo esté bien y dice EXACTAMENTE qué falta."""
import shutil

import config


def run():
    fatal, warn = [], []

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            fatal.append(f"No encuentro {tool}. Usa el Dockerfile o instala ffmpeg.")

    import db

    try:
        db.sb.table("jobs").select("id").limit(1).execute()
    except Exception as e:  # noqa: BLE001
        fatal.append(f"No puedo hablar con Supabase ({str(e)[:150]}). Revisa SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en worker/.env.")
    else:
        try:
            names = [getattr(b, "name", None) or (b.get("name") if isinstance(b, dict) else None) for b in db.sb.storage.list_buckets()]
            if "clips" not in names:
                fatal.append("No existe el bucket 'clips' en Supabase Storage (corre 0001_init.sql o créalo a mano, privado).")
        except Exception as e:  # noqa: BLE001
            warn.append(f"No pude listar los buckets: {str(e)[:120]}")
        try:
            db.sb.table("sources").select("stop_requested,progress").limit(1).execute()
            db.sb.table("worker_status").select("id").limit(1).execute()
        except Exception:  # noqa: BLE001
            fatal.append("Falta la migración 0003_live.sql: pégala en Supabase > SQL Editor y ejecútala.")

    if config.GROQ_API_KEY:
        if not config.GROQ_API_KEY.startswith("gsk_"):
            warn.append("Tu GROQ_API_KEY no empieza con 'gsk_': probablemente no es una llave de Groq.")
        try:
            import requests

            r = requests.get("https://api.groq.com/openai/v1/models",
                             headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"}, timeout=15)
            if r.status_code in (401, 403):
                fatal.append("Groq rechazó tu GROQ_API_KEY (inválida). Crea una nueva en console.groq.com.")
        except Exception as e:  # noqa: BLE001
            warn.append(f"No pude comprobar Groq (¿sin internet?): {str(e)[:100]}")

    for w in warn:
        print("⚠ ", w, flush=True)
    if fatal:
        print("\n✗ El worker NO puede arrancar:", flush=True)
        for f in fatal:
            print("  -", f, flush=True)
        raise SystemExit(1)
    print("✓ Revisión inicial correcta (Supabase, bucket, ffmpeg, llaves).", flush=True)
