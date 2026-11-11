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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip().strip("\"'").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Proveedor que se prueba primero (llm.py rota solo a los demás si se queda sin cupo). Por defecto: anthropic solo si hay llave.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER") or ("anthropic" if ANTHROPIC_API_KEY else "groq")

# Transcripción: si hay GROQ_API_KEY se usa la nube (rápido); si no, faster-whisper local.
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
LANGUAGE = os.environ.get("LANGUAGE", "es")

# "crop" = el video llena TODA la pantalla vertical 9:16 (por defecto); "blur" = video chico centrado con fondo difuminado
CLIP_LAYOUT = (os.environ.get("CLIP_LAYOUT") or "crop").strip().lower()
# Encuadre: "auto" = sigue la cara de quien habla (necesita scikit-image); "center" = fijo según CLIP_FOCUS_X
CLIP_FRAMING = (os.environ.get("CLIP_FRAMING") or "auto").strip().lower()
# Calidad: CRF más bajo = más nítido y más pesado (17-20 va bien); nitidez 0 = apagada, 0.5 suave, 1.0 fuerte
CLIP_CRF = int(os.environ.get("CLIP_CRF") or 18)
CLIP_PRESET = (os.environ.get("CLIP_PRESET") or "fast").strip()   # ultrafast ... veryfast, fast, medium, slow
try:
    CLIP_SHARPEN = min(1.5, max(0.0, float(os.environ.get("CLIP_SHARPEN") or 0.5)))
except ValueError:
    CLIP_SHARPEN = 0.5
# Encuadre horizontal del recorte: 0 = izquierda, 0.5 = centro, 1 = derecha (útil si la persona no está en el centro)
try:
    CLIP_FOCUS_X = min(1.0, max(0.0, float(os.environ.get("CLIP_FOCUS_X") or 0.5)))
except ValueError:
    CLIP_FOCUS_X = 0.5
COOKIES_FILE = os.environ.get("COOKIES_FILE", "")  # cookies.txt de YouTube si te pide "confirmar que no eres un bot"

# --- NUEVO: Ruta del logo para el Brand Kit ---
LOGO_PATH = os.environ.get("LOGO_PATH", "")

POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "5"))
WORK_DIR = Path(os.environ.get("WORK_DIR", "./work"))

# --- Modo En vivo ---
SEGMENT_SECONDS = int(os.environ.get("SEGMENT_SECONDS", "120"))   # tamaño de cada trozo grabado
REVIEW_MINUTES = int(os.environ.get("REVIEW_MINUTES", "2"))       # cada cuánto revisa la IA (si la web no lo manda)
LIVE_MIN_SCORE = int(os.environ.get("LIVE_MIN_SCORE", "55"))      # puntaje mínimo para crear un clip en vivo
