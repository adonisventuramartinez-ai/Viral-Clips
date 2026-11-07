import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def _e(name, default=""):
    return (os.environ.get(name) or default).strip()


SUPABASE_URL = _e("SUPABASE_URL") or _e("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = _e("SUPABASE_SERVICE_ROLE_KEY", "")

ANTHROPIC_API_KEY = _e("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = _e("GROQ_API_KEY", "")
CLAUDE_MODEL = _e("CLAUDE_MODEL", "claude-sonnet-5-5")
GROQ_MODEL = _e("GROQ_MODEL", "llama-3.3-70b-versatile")

# Quién elige los momentos: "groq" (gratis) o "anthropic" (de pago). Por defecto: anthropic solo si hay llave.
LLM_PROVIDER = _e("LLM_PROVIDER") or ("anthropic" if ANTHROPIC_API_KEY else "groq")

# Transcripción: si hay GROQ_API_KEY se usa la nube (rápido); si no, faster-whisper local.
WHISPER_MODEL = _e("WHISPER_MODEL", "small")
LANGUAGE = _e("LANGUAGE", "es")

# "blur" = video completo centrado con fondo difuminado; "crop" = recorte centrado a 9:16
CLIP_LAYOUT = _e("CLIP_LAYOUT", "blur")
COOKIES_FILE = _e("COOKIES_FILE", "")  # cookies.txt de YouTube si te pide "confirmar que no eres un bot"

POLL_SECONDS = int(_e("POLL_SECONDS", "5"))
WORK_DIR = Path(_e("WORK_DIR", "./work"))
