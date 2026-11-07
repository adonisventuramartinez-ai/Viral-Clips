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

    if config.GROQ_API_KEY and not config.GROQ_API_KEY.startswith("gsk_"):
        warn.append("Tu GROQ_API_KEY no empieza con 'gsk_': probablemente no es una llave de Groq.")

    if config.CLIP_LAYOUT == "crop" and config.CLIP_FRAMING == "auto":
        try:
            import framing
            framing._load()
        except Exception as e:  # noqa: BLE001
            warn.append(f"El encuadre automatico no esta disponible ({type(e).__name__}); los clips saldran centrados. "
                        "Reconstruye el worker (docker build) para instalar scikit-image.")

    import llm

    names = llm.configured()
    if not names:
        fatal.append("No hay ninguna llave de IA en worker/.env. Pon al menos una: GROQ_API_KEY (console.groq.com), "
                     "CEREBRAS_API_KEY, GEMINI_API_KEY, MISTRAL_API_KEY, OPENROUTER_API_KEY o GITHUB_MODELS_TOKEN.")
    else:
        print("Probando las llaves de IA (una petición mínima a cada una)…", flush=True)
        results = llm.check_all()
        for name, state, detail in results:
            mark = {"ok": "✓", "cupo": "⏳", "mala": "✗"}[state]
            print(f"  {mark} {name}: {detail}", flush=True)
        if not any(st in ("ok", "cupo") for _, st, _ in results):
            fatal.append("Ninguna llave de IA funciona (mira la lista de arriba). Corrige al menos una en worker/.env.")
        elif sum(1 for _, st, _ in results if st == "ok") == 1:
            warn.append("Solo 1 proveedor de IA funciona: si se queda sin cupo no habrá a quién cambiar. Agrega otra llave (ver .env.example).")

    for w in warn:
        print("⚠ ", w, flush=True)
    if fatal:
        print("\n✗ El worker NO puede arrancar:", flush=True)
        for f in fatal:
            print("  -", f, flush=True)
        raise SystemExit(1)
    print("✓ Revisión inicial correcta (Supabase, bucket, ffmpeg, IA).", flush=True)
