"""Cola de trabajos más robusta: errores explicados en español, reintentos con espera y prioridades.
Solo decide QUÉ hacer con un error; db.py es quien habla con Supabase."""
import re

import config

# (patrón en el texto del error, mensaje para la persona, ¿vale la pena reintentar?)
_RULES = [
    (r"sign in to confirm|cookies|login required|private video|members.only", "YouTube pidió iniciar sesión. Renueva www.youtube.com_cookies.txt y vuelve a intentar.", False),
    (r"video unavailable|has been removed|this video is not available|no longer available", "El video ya no está disponible (borrado o privado).", False),
    (r"unsupported url|not a valid url|is not a valid", "El link no es de un video que se pueda descargar.", False),
    (r"no se detect[oó] voz", "No se oye voz en el video, no hay nada que transcribir.", False),
    (r"no encontr[oó] momentos", "La IA no encontró momentos buenos. Prueba otro tipo de contenido o un video más largo.", False),
    (r"ya no existe|no se pueden re-renderizar|debe durar entre", None, False),   # mensajes propios: se dejan tal cual
    (r"429|rate.?limit|quota|too many requests|resource.?exhausted", "La IA llegó a su límite de uso. Reintento en unos minutos.", True),
    (r"timed? ?out|timeout|connection (reset|aborted|refused|error)|temporary failure|name resolution|network|502|503|504|ssl", "Falló la conexión a internet. Reintento en unos minutos.", True),
    (r"no space left|disk full|errno 28", "Se llenó el disco del worker. Libera espacio y reintenta.", False),
    (r"out of memory|cannot allocate|killed|memoryerror", "El equipo se quedó sin memoria. Cierra programas o baja la calidad a 720p.", True),
    (r"ffmpeg|ffprobe|invalid data found|moov atom", "ffmpeg no pudo procesar el video. Reintento una vez más.", True),
    (r"supabase|postgrest|jwt|storage", "Falló la conexión con Supabase. Reintento en unos minutos.", True),
]


def explain(exc) -> tuple[str, bool]:
    """(mensaje claro, ¿reintentar?) para cualquier excepción. Lo desconocido se reintenta una vez."""
    raw = f"{type(exc).__name__}: {exc}"
    low = raw.lower()
    for pat, msg, retry in _RULES:
        if re.search(pat, low):
            return (msg or str(exc)[:200]), retry
    return f"Error inesperado: {raw[:200]}", True


def delay_for(attempt: int) -> int:
    """Segundos de espera antes del reintento número `attempt` (1, 2, ...): 1 min, 5 min, 15 min."""
    steps = config.JOB_RETRY_DELAYS
    return steps[min(max(attempt, 1), len(steps)) - 1]


def decide(job, exc) -> dict:
    """Qué hacer con un trabajo que falló: {'retry': bool, 'delay': seg, 'message': texto claro, 'detail': técnico}."""
    msg, retry = explain(exc)
    attempts = int(job.get("attempts") or 1)
    limit = int(job.get("max_attempts") or config.JOB_MAX_ATTEMPTS)
    can = retry and attempts < limit
    return {"retry": can, "delay": delay_for(attempts) if can else 0,
            "message": msg if can else (msg if attempts < 2 or not retry else f"{msg} (falló {attempts} veces)"),
            "detail": f"{type(exc).__name__}: {exc}"[:500]}


# Prioridad según el tipo de trabajo: un directo no puede esperar, un ajuste de clip lo espera una persona
PRIORITY = {"record": 10, "clip": 5, "download": 0}


def priority_of(job_type: str, urgent: bool = False) -> int:
    return PRIORITY.get(job_type, 0) + (3 if urgent else 0)


def fail(job, exc, source_id=None):
    """Un trabajo falló: lo explica en español y decide si se reintenta (con espera) o se queda en error."""
    import db
    import logx
    d = decide(job, exc)
    if d["retry"]:
        print(f"  ✖ {d['message']} Intento {job.get('attempts', 1)} de {job.get('max_attempts') or config.JOB_MAX_ATTEMPTS}; "
              f"vuelvo a probar en {logx.fmt_dur(d['delay'])}.", flush=True)
        db.retry_job(job["id"], d["delay"], error=d["detail"])
        if source_id:
            db.set_source(source_id, status="queued", error=f"{d['message']} Reintentando en {logx.fmt_dur(d['delay'])}…"[:500])
    else:
        print(f"  ✖ {d['message']}", flush=True)
        print(f"    detalle técnico: {d['detail']}", flush=True)
        db.finish_job(job["id"], ok=False, error=d["detail"])
        if source_id:
            db.set_source(source_id, status="error", error=d["message"][:500])
