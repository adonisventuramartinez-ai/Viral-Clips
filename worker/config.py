import os
import re
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def _clean_key(k):
    return (k or "").strip().strip("\"'").strip()


def groq_keys():
    """Todas las llaves de Groq (sin límite: 3, 20, 50...), sin repetir y en orden.

    Se leen de cualquiera de estos sitios (puedes mezclarlos):
      GROQ_KEYS=gsk_a,gsk_b,gsk_c        (separadas por coma, espacio o salto de línea)
      GROQ_API_KEY=gsk_a                 (también acepta varias separadas por coma)
      GROQ_API_KEY_2=gsk_b ... GROQ_API_KEY_99=...
      worker/groq_keys.txt               (una llave por línea; las líneas con # se ignoran)
    Se lee en cada llamada, así que agregar una cuenta no requiere tocar el código.
    """
    raw = [os.environ.get("GROQ_KEYS", ""), os.environ.get("GROQ_API_KEY", "")]
    raw += [os.environ.get(f"GROQ_API_KEY_{i}", "") for i in range(1, 100)]
    path = Path(os.environ.get("GROQ_KEYS_FILE") or Path(__file__).with_name("groq_keys.txt"))
    try:
        raw.append("\n".join(l.split("#")[0] for l in path.read_text(encoding="utf-8").splitlines()))
    except OSError:
        pass
    out = []
    for blob in raw:
        for k in re.split(r"[,\s;]+", blob or ""):
            k = _clean_key(k)
            if k and k not in out:
                out.append(k)
    return out


GROQ_API_KEY = ",".join(groq_keys())   # compatibilidad: todas juntas
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
CLIP_CRF = int(os.environ.get("CLIP_CRF") or 17)
CLIP_PRESET = (os.environ.get("CLIP_PRESET") or "medium").strip()   # ultrafast ... veryfast, fast, medium, slow
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
SEGMENT_SECONDS = int(os.environ.get("SEGMENT_SECONDS", "45"))    # tamaño de cada trozo grabado (más corto = clips más rápido)
REVIEW_MINUTES = int(os.environ.get("REVIEW_MINUTES", "2"))       # cada cuánto revisa la IA (si la web no lo manda)
LIVE_MIN_SCORE = int(os.environ.get("LIVE_MIN_SCORE", "55"))      # puntaje mínimo para crear un clip en vivo

LIVE_MAX_NEW = int(os.environ.get("LIVE_MAX_NEW", "3"))           # máximo de clips nuevos por cada revisión en vivo
LIVE_CHAT = (os.environ.get("LIVE_CHAT") or "1").strip().lower() not in ("0", "false", "no", "off")   # leer el chat del directo
LIVE_RECONNECTS = int(os.environ.get("LIVE_RECONNECTS", "6"))     # reconexiones seguidas antes de rendirse
WATCH_SECONDS = int(os.environ.get("WATCH_SECONDS", "120"))       # cada cuánto mira si tus canales entraron en vivo

# --- Calidad de la IA ---
RERANK = (os.environ.get("RERANK") or "1").strip().lower() not in ("0", "false", "no", "off")   # segunda pasada que re-puntúa candidatos
SNAP_CUTS = (os.environ.get("SNAP_CUTS") or "1").strip().lower() not in ("0", "false", "no", "off")  # cortar en pausas/finales de frase

# --- Quién habla (opcional): necesita `pip install pyannote.audio` y una llave gratis de huggingface.co ---
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()

# --- Modo Original (Facebook premia aporte propio; ver original.py) ---
ORIGINAL_MODE = (os.environ.get("ORIGINAL_MODE") or "1").strip().lower() not in ("0", "false", "no", "off")
SHOW_NAME = os.environ.get("SHOW_NAME", "La Casa de Alofoke 3")
PAGE_NAME = os.environ.get("PAGE_NAME", "Tu página")
CREDIT_LINE = os.environ.get("CREDIT_LINE", "Contenido de La Casa de Alofoke, usado con permiso de Alofoke.")
NARRATOR_VOICE = os.environ.get("NARRATOR_VOICE", "es-DO-EmilioNeural")   # es-DO-RamonaNeural = voz femenina dominicana
# --- Publicación automática en Facebook (opcional) ---
FB_AUTOPUBLISH = (os.environ.get("FB_AUTOPUBLISH") or "0").strip().lower() in ("1", "true", "yes", "on")
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "").strip()
FB_PAGE_TOKEN = os.environ.get("FB_PAGE_TOKEN", "").strip()
FB_MIN_SCORE = int(os.environ.get("FB_MIN_SCORE") or 75)       # solo publica clips con este puntaje o más
FB_MAX_PER_JOB = int(os.environ.get("FB_MAX_PER_JOB") or 3)    # tope por video procesado


# --- Transcripción: ayuda a Whisper con nombres propios y jerga (Groq acepta ~220 tokens) ---
CAST_NAMES = [n.strip() for n in re.split(r"[,;\n]+", os.environ.get("CAST_NAMES", "")) if n.strip()]
WHISPER_PROMPT = os.environ.get("WHISPER_PROMPT", "").strip()
TRANSCRIBE_CHUNK = int(os.environ.get("TRANSCRIBE_CHUNK") or 600)       # segundos por llamada a Whisper
TRANSCRIBE_PAD = int(os.environ.get("TRANSCRIBE_PAD") or 8)             # segundos extra a cada lado para no cortar palabras
ANALYSIS_OVERLAP = int(os.environ.get("ANALYSIS_OVERLAP") or 90)        # solape entre ventanas que lee la IA


def whisper_prompt():
    """Texto que se le pasa a Whisper: nombres del elenco y jerga dominicana, para que no los escriba mal."""
    if WHISPER_PROMPT:
        return WHISPER_PROMPT[:700]
    names = ", ".join(dict.fromkeys(["Alofoke"] + CAST_NAMES))
    txt = (f"Conversación en español dominicano con {names}. "
           "Dicen: klk, qué lo qué, vaina, tíguere, dime a ver, manín, jevi, pariguayo, chercha, colmado, guagua, mi hermano.")
    return txt[:700]


# --- Parte 3: detección mejorada ---
def _flag(name, default="1"):
    return (os.environ.get(name) or default).strip().lower() not in ("0", "false", "no", "off")


DETECT_AUDIO = _flag("DETECT_AUDIO")          # disparos/explosiones por audio (GTA y juegos)
DETECT_SCREEN = _flag("DETECT_SCREEN")        # WASTED / BUSTED / MISSION PASSED / estrellas (GTA)
DETECT_ARGUMENT = _flag("DETECT_ARGUMENT")    # discusiones (Reality)
DEDUPE = _flag("DEDUPE")                      # quitar clips repetidos (otra cámara, mismo momento)
try:
    DEDUPE_THRESHOLD = min(0.95, max(0.3, float(os.environ.get("DEDUPE_THRESHOLD") or 0.55)))
except ValueError:
    DEDUPE_THRESHOLD = 0.55
DEDUPE_HOURS = int(os.environ.get("DEDUPE_HOURS") or 48)     # compara con los clips de las últimas N horas
# Verificación con imágenes: auto = solo GTA/juegos/reality y solo si hay un modelo con visión; 1 = siempre; 0 = apagada
VERIFY_IMAGES = (os.environ.get("VERIFY_IMAGES") or "auto").strip().lower()
VERIFY_TOP = int(os.environ.get("VERIFY_TOP") or 12)         # cuántos candidatos revisa con imágenes (los mejores)
VERIFY_FRAMES = min(5, max(2, int(os.environ.get("VERIFY_FRAMES") or 3)))
