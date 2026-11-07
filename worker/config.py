import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Quién elige los momentos: "groq" (gratis) o "anthropic" (de pago). Por defecto: anthropic solo si hay llave.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER") or ("anthropic" if ANTHROPIC_API_KEY else "groq")

# Transcripción: si hay GROQ_API_KEY se usa la nube (rápido); si no, faster-whisper local.
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
LANGUAGE = os.environ.get("LANGUAGE", "es")

# "blur" = video completo centrado con fondo difuminado; "crop" = recorte centrado a 9:16
CLIP_LAYOUT = os.environ.get("CLIP_LAYOUT", "blur")
COOKIES_FILE = os.environ.get("COOKIES_FILE", "")  # cookies.txt de YouTube si te pide "confirmar que no eres un bot"

POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "5"))
WORK_DIR = Path(os.environ.get("WORK_DIR", "./work"))

# --- Modo En vivo ---
SEGMENT_SECONDS = int(os.environ.get("SEGMENT_SECONDS", "120"))   # tamaño de cada trozo grabado
REVIEW_MINUTES = int(os.environ.get("REVIEW_MINUTES", "2"))       # cada cuánto revisa la IA (si la web no lo manda)
LIVE_MIN_SCORE = int(os.environ.get("LIVE_MIN_SCORE", "55"))      # puntaje mínimo para crear un clip en vivo
