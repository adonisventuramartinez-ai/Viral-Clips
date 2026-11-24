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
    raw += [os.environ.get(f"GROQ_API_KEY_{i}", "") for i in range(1, 1000)]   # hasta 999 llaves por variable de entorno
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
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

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
CLIP_CRF = int(os.environ.get("CLIP_CRF") or 16)
CLIP_PRESET = (os.environ.get("CLIP_PRESET") or "medium").strip()   # ultrafast ... veryfast, fast, medium, slow
try:
    # El recorte 9:16 de un directo 1080p se estira ~1.8x: CAS recupera detalle sin el halo del unsharp agresivo.
    CLIP_CAS = min(1.0, max(0.0, float(os.environ.get("CLIP_CAS") or 0.65)))
except ValueError:
    CLIP_CAS = 0.65
try:
    CLIP_SHARPEN = min(1.5, max(0.0, float(os.environ.get("CLIP_SHARPEN") or 0.35)))
except ValueError:
    CLIP_SHARPEN = 0.35
# Encuadre horizontal del recorte: 0 = izquierda, 0.5 = centro, 1 = derecha (útil si la persona no está en el centro)
try:
    CLIP_FOCUS_X = min(1.0, max(0.0, float(os.environ.get("CLIP_FOCUS_X") or 0.5)))
except ValueError:
    CLIP_FOCUS_X = 0.5
# Subtítulos (render.py) - ajustables sin tocar código:
try:
    CLIP_SUB_SIZE = min(140, max(40, int(os.environ.get("CLIP_SUB_SIZE") or 82)))       # tamaño base de los subtítulos
except ValueError:
    CLIP_SUB_SIZE = 82
try:
    CLIP_SUB_SHADOW = min(10, max(0, int(os.environ.get("CLIP_SUB_SHADOW") or 5)))      # sombra de los subtítulos
except ValueError:
    CLIP_SUB_SHADOW = 5
try:
    CLIP_SUB_BLUR = min(2.0, max(0.0, float(os.environ.get("CLIP_SUB_BLUR") or 0.3)))  # blur de los subtítulos
except ValueError:
    CLIP_SUB_BLUR = 0.3
try:
    CLIP_SUB_SHADOW = min(10, max(0, int(os.environ.get("CLIP_SUB_SHADOW") or 5)))      # sombra de los subtítulos
except ValueError:
    CLIP_SUB_SHADOW = 5
try:
    CLIP_SUB_OUTLINE = min(14, max(0, int(os.environ.get("CLIP_SUB_OUTLINE") or 7)))     # contorno de los subtítulos
except ValueError:
    CLIP_SUB_OUTLINE = 7
try:
    CLIP_HOOK_SIZE = min(100, max(40, int(os.environ.get("CLIP_HOOK_SIZE") or 72)))      # tamaño del gancho arriba del clip
except ValueError:
    CLIP_HOOK_SIZE = 72
# Sincronía voz/subtítulos: Whisper y Groq marcan la palabra ~0.35-0.5 s DESPUÉS de que empieza a oírse
# (por eso "el audio va adelantado": se oye primero y el texto sale después). Negativo = el texto entra antes.
# Se puede afinar en .env con SUB_SYNC_OFFSET (0 desactiva el ajuste).
try:
    SUB_SYNC_OFFSET = min(1.0, max(-1.0, float(os.environ.get("SUB_SYNC_OFFSET") or -0.35)))
except ValueError:
    SUB_SYNC_OFFSET = -0.35

# IA (viral.py) - ajustables sin tocar código:
try:
    VIRAL_POWER_BOOST = min(2.0, max(0.5, float(os.environ.get("VIRAL_POWER_BOOST") or 1.0)))   # multiplicador de palabras de poder en el puntaje
except ValueError:
    VIRAL_POWER_BOOST = 1.0
try:
    VIRAL_HASHTAG_LIMIT = min(8, max(3, int(os.environ.get("VIRAL_HASHTAG_LIMIT") or 6)))   # máximo de hashtags en el paquete viral
except ValueError:
    VIRAL_HASHTAG_LIMIT = 6

# Hook (hook.py) - ajustables sin tocar código:
try:
    HOOK_MAX_SHIFT = min(10.0, max(2.0, float(os.environ.get("HOOK_MAX_SHIFT") or 6.0)))   # segundos máximos para mover el inicio
except ValueError:
    HOOK_MAX_SHIFT = 6.0
try:
    HOOK_MIN_GAIN = min(30, max(5, int(os.environ.get("HOOK_MIN_GAIN") or 10)))   # ganancia mínima para mover el inicio
except ValueError:
    HOOK_MIN_GAIN = 10

# Calibración del encuadre (framing.py) - ajustables sin tocar código:
try:
    CLIP_MIN_DWELL = min(10, max(1, int(os.environ.get("CLIP_MIN_DWELL") or 3)))          # muestras seguidas antes de mover la cámara
except ValueError:
    CLIP_MIN_DWELL = 3
try:
    CLIP_MIN_GAP = min(5.0, max(0.5, float(os.environ.get("CLIP_MIN_GAP") or 3.0)))       # segundos mínimos entre paneos
except ValueError:
    CLIP_MIN_GAP = 3.0
try:
    CLIP_URGENT_EDGE = min(0.6, max(0.1, float(os.environ.get("CLIP_URGENT_EDGE") or 0.36)))  # si la cara cae en el exterior, reacciona rápido
except ValueError:
    CLIP_URGENT_EDGE = 0.36
try:
    CLIP_RAMP = min(2.0, max(0.2, float(os.environ.get("CLIP_RAMP") or 0.55)))            # duración del paneo
except ValueError:
    CLIP_RAMP = 0.55
try:
    CLIP_MIN_COVERAGE = min(0.5, max(0.05, float(os.environ.get("CLIP_MIN_COVERAGE") or 0.25)))  # si hay caras en menos de esta fracción, usa el centro
except ValueError:
    CLIP_MIN_COVERAGE = 0.25
# --- Cámara del en vivo: análisis más fino sin frenar la grabación ---
try:
    CLIP_CAM_DET_W = min(1280, max(640, int(os.environ.get("CLIP_CAM_DET_W") or 960)))
except ValueError:
    CLIP_CAM_DET_W = 960
try:
    CLIP_CAM_FPS = min(6.0, max(2.0, float(os.environ.get("CLIP_CAM_FPS") or 3.5)))
except ValueError:
    CLIP_CAM_FPS = 3.5
try:
    CLIP_CAM_FACE_MIN = min(0.08, max(0.015, float(os.environ.get("CLIP_CAM_FACE_MIN") or 0.035)))
except ValueError:
    CLIP_CAM_FACE_MIN = 0.035
COOKIES_FILE = os.environ.get("COOKIES_FILE", "")  # cookies.txt de YouTube si te pide "confirmar que no eres un bot"

# --- NUEVO: Ruta del logo para el Brand Kit ---
LOGO_PATH = os.environ.get("LOGO_PATH", "")

POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "5"))
# Absoluta: varios subprocess de ffmpeg corren con cwd=work; si fuera relativa,
# las rutas "work/<sid>/..." se duplicarían y no encontrarían el archivo de entrada.
WORK_DIR = Path(os.environ.get("WORK_DIR", "./work")).resolve()

# --- Modo En vivo ---
SEGMENT_SECONDS = int(os.environ.get("SEGMENT_SECONDS", "45"))    # tamaño de cada trozo grabado (más corto = clips más rápido)
# Grabar el directo a 720p y estirar el recorte 9:16 a 1080 dejaba la cámara borrosa. Piso mínimo de captura:
LIVE_MIN_HEIGHT = int(os.environ.get("LIVE_MIN_HEIGHT") or 1080)
REVIEW_MINUTES = int(os.environ.get("REVIEW_MINUTES", "2"))       # cada cuánto revisa la IA (si la web no lo manda)
LIVE_MIN_SCORE = int(os.environ.get("LIVE_MIN_SCORE", "55"))      # puntaje mínimo para crear un clip en vivo

LIVE_MAX_NEW = int(os.environ.get("LIVE_MAX_NEW", "5"))           # máximo de clips nuevos por cada revisión en vivo
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
FB_MAX_PER_JOB = int(os.environ.get("FB_MAX_PER_JOB") or 5)    # tope por video procesado
SCHEDULE_CHECK_SECONDS = int(os.environ.get("SCHEDULE_CHECK_SECONDS") or 60)   # cada cuánto revisa si hay clips programados
PACK = (os.environ.get("PACK") or "1").strip().lower() not in ("0", "false", "no", "off")    # paquete de textos por red + ganchos (una llamada de IA por clip)
THUMBS = (os.environ.get("THUMBS") or "1").strip().lower() not in ("0", "false", "no", "off")  # miniatura automática


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


# --- Parte 4: audio, efectos, cámara de streamer y GPU ---
CLIP_BLEEP = _flag("CLIP_BLEEP")              # pitido en groserías (y subtítulo censurado)
BLEEP_WORDS = os.environ.get("BLEEP_WORDS", "")   # palabras extra a pitar, separadas por coma
BLEEP_KEEP = os.environ.get("BLEEP_KEEP", "")     # palabras que NO se pitan aunque estén en la lista
CLIP_LOUDNORM = _flag("CLIP_LOUDNORM")        # volumen parejo (LUFS)
try:
    CLIP_LUFS = min(-9.0, max(-23.0, float(os.environ.get("CLIP_LUFS") or -14)))
except ValueError:
    CLIP_LUFS = -14.0
# zoom y cámara lenta: auto = lo decide el tipo de contenido (GTA y Juegos: ambos; GTA RP y Reality: solo zoom); 1 = siempre; 0 = nunca
CLIP_ZOOM = (os.environ.get("CLIP_ZOOM") or "auto").strip().lower()
CLIP_SLOWMO = (os.environ.get("CLIP_SLOWMO") or "auto").strip().lower()
CLIP_TIGHTEN = (os.environ.get("CLIP_TIGHTEN") or "auto").strip().lower()   # quitar silencios y muletillas: auto (según el tipo) | 1 | 0
INTRO_MODE = (os.environ.get("INTRO_MODE") or "cold").strip().lower()       # "cold" (por defecto) = el clip arranca ya, con el texto encima | "card" = tarjeta con voz ANTES del clip (la gente se va en esos 2 s)
if INTRO_MODE not in ("cold", "card"):
    INTRO_MODE = "cold"
SMART_START = _flag("SMART_START")   # mover el inicio del clip a la primera frase fuerte (saltar saludos y muletillas) y cambiar ganchos genéricos
try:
    CLIP_MAX_MB = min(49.0, max(8.0, float(os.environ.get("CLIP_MAX_MB") or 44)))   # tope por clip: Supabase rechaza archivos de 50 MB o más
except ValueError:
    CLIP_MAX_MB = 44.0
# --- Modo Transformar (video externo -> clip "blindado" para Facebook) ---
try:
    TRANSFORM_MAX_MB = min(49.0, max(5.0, float(os.environ.get("TRANSFORM_MAX_MB") or 45)))  # tope del archivo subido
except ValueError:
    TRANSFORM_MAX_MB = 45.0
try:
    TRANSFORM_MAX_SECONDS = max(30, min(3600, int(os.environ.get("TRANSFORM_MAX_SECONDS") or 600)))  # recorte de seguridad
except ValueError:
    TRANSFORM_MAX_SECONDS = 600
try:
    TRANSFORM_DEFAULT_SCORE = max(35, min(99, int(os.environ.get("TRANSFORM_DEFAULT_SCORE") or 78)))
except ValueError:
    TRANSFORM_DEFAULT_SCORE = 78
TRANSFORM_ALWAYS_ORIGINAL = (os.environ.get("TRANSFORM_ALWAYS_ORIGINAL") or "1").strip().lower() not in ("0", "false", "no", "off")
# Transformar arranca en frío: video + gancho en el cuadro 0, voz propia mezclada SOBRE el video.
# La tarjeta anterior ("card") regalaba 2 s en los que la gente se iba; queda solo como opción manual.
TRANSFORM_INTRO = (os.environ.get("TRANSFORM_INTRO") or "cold").strip().lower()
if TRANSFORM_INTRO not in ("cold", "card"):
    TRANSFORM_INTRO = "cold"
# --- Crear con IA (texto -> video, 60 s vertical) ---
HF_TOKEN = (os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_API_KEY") or "").strip()
HF_MODEL = os.environ.get("HF_MODEL") or "damo-vilab/text-to-video-ms-1.7b"
REPLICATE_API_TOKEN = (os.environ.get("REPLICATE_API_TOKEN") or "").strip()
REPLICATE_VERSION = (os.environ.get("REPLICATE_VERSION") or "").strip()   # owner/model:hash (opcional, plan B)
try:
    IA_CLIPS = max(1, min(20, int(os.environ.get("IA_CLIPS") or 4)))
except ValueError:
    IA_CLIPS = 4
try:
    IA_CLIP_SECONDS = max(2, min(60, int(os.environ.get("IA_CLIP_SECONDS") or 15)))
except ValueError:
    IA_CLIP_SECONDS = 15
try:
    IA_TOTAL_SECONDS = max(5, min(300, int(os.environ.get("IA_TOTAL_SECONDS") or 60)))
except ValueError:
    IA_TOTAL_SECONDS = 60
try:
    IA_REQUEST_TIMEOUT = max(30, min(900, int(os.environ.get("IA_REQUEST_TIMEOUT") or 300)))
except ValueError:
    IA_REQUEST_TIMEOUT = 300
try:
    IA_MAX_RETRIES = max(1, min(10, int(os.environ.get("IA_MAX_RETRIES") or 4)))
except ValueError:
    IA_MAX_RETRIES = 4
try:
    IA_MAX_WAIT = max(1, min(60, int(os.environ.get("IA_MAX_WAIT") or 25)))
except ValueError:
    IA_MAX_WAIT = 25
IA_MUSIC_URL = (os.environ.get("IA_MUSIC_URL") or "").strip()   # pista propia opcional; si no, se sintetiza
IA_STYLE_DEFAULT = (os.environ.get("IA_STYLE_DEFAULT") or "realista").strip().lower()
try:
    CLIP_SLOW_RATE = min(0.9, max(0.5, float(os.environ.get("CLIP_SLOW_RATE") or 0.5)))
except ValueError:
    CLIP_SLOW_RATE = 0.5
CLIP_FACECAM = _flag("CLIP_FACECAM")          # buscar el recuadro de la cámara del streamer en el modo dividido
# Codificador de video: auto (prueba GPU y si no hay usa CPU) | cpu | nvenc (NVIDIA) | qsv (Intel) | amf (AMD) | videotoolbox (Mac)
CLIP_ENCODER = (os.environ.get("CLIP_ENCODER") or "auto").strip().lower()
# Subtítulos con un color por persona: auto = solo si hay pyannote + HF_TOKEN; 1 = intentar siempre; 0 = apagado
SUBS_PER_SPEAKER = (os.environ.get("SUBS_PER_SPEAKER") or "auto").strip().lower()


# --- Parte 5: quién habla ---
VOICES = _flag("VOICES")                      # separar voces por timbre y tono (P1, P2...) sin instalar nada
VOICE_MAX = min(10, max(2, int(os.environ.get("VOICE_MAX") or 6)))      # máximo de personas distintas
try:
    VOICE_THRESHOLD = min(6.0, max(0.5, float(os.environ.get("VOICE_THRESHOLD") or 1.6)))   # más bajo = separa más (y se equivoca más)
except ValueError:
    VOICE_THRESHOLD = 1.6


# --- Mejora 4: cola, reintentos y logs ---
JOB_MAX_ATTEMPTS = min(6, max(1, int(os.environ.get("JOB_MAX_ATTEMPTS") or 3)))     # intentos por trabajo antes de dejarlo en error
try:
    JOB_RETRY_DELAYS = [max(5, int(x)) for x in (os.environ.get("JOB_RETRY_DELAYS") or "60,300,900").split(",") if x.strip()] or [60, 300, 900]
except ValueError:
    JOB_RETRY_DELAYS = [60, 300, 900]                                                # segundos de espera entre intentos
LOG_DIR = Path(os.environ.get("LOG_DIR", "./logs"))                                 # carpeta de los logs (worker.log, rota solo)
LOG_MAX_MB = min(200, max(1, int(os.environ.get("LOG_MAX_MB") or 5)))


# --- Parte 7: área "Hacerlo viral" (todo opcional) ---
VIRAL = _flag("VIRAL")                                  # pasar cada clip por el área viral (título, hashtags, miniatura, puntaje)
VIRAL_AUTO_TITLE = _flag("VIRAL_AUTO_TITLE")            # poner el mejor título solo (el original se guarda en viral.title_original)
VIRAL_THUMB_AB = _flag("VIRAL_THUMB_AB")                # segunda miniatura (otro cuadro, otro texto) para probar A/B
VIRAL_MIN_SCORE = int(os.environ.get("VIRAL_MIN_SCORE") or 70)      # desde aquí el clip queda "listo" para publicar
VIRAL_REVIEW_SCORE = int(os.environ.get("VIRAL_REVIEW_SCORE") or 55)  # entre este y el mínimo: lo revisas tú; debajo: descartado
VIRAL_BACKFILL_DAYS = int(os.environ.get("VIRAL_BACKFILL_DAYS") or 7)  # clips sin análisis (en vivo, rehechos) de los últimos N días
VIRAL_TICK_SECONDS = int(os.environ.get("VIRAL_TICK_SECONDS") or 60)
# Mejores horas para publicar (hora de tu país) y huso. Valores por defecto razonables para RD; en la Parte 4 se aprenden de tus datos.
POST_SLOTS = [s.strip() for s in (os.environ.get("POST_SLOTS") or "12:30,19:00,21:30").split(",") if s.strip()]
POST_TZ_OFFSET = float(os.environ.get("POST_TZ_OFFSET") or -4)       # República Dominicana = UTC-4 todo el año
POST_MIN_GAP_MIN = int(os.environ.get("POST_MIN_GAP_MIN") or 90)     # separación mínima entre dos publicaciones
POST_MAX_PER_DAY = int(os.environ.get("POST_MAX_PER_DAY") or 6)


# --- Parte 8: cola de publicación automática (todo opcional; APAGADA por defecto) ---
AUTO_QUEUE = (os.environ.get("AUTO_QUEUE") or "0").strip().lower() in ("1", "true", "yes", "on")   # programar solo los clips "listos" de la Parte 7
AUTO_NETWORKS = [n.strip().lower() for n in (os.environ.get("AUTO_NETWORKS") or "").split(",") if n.strip()]   # vacío = todas las que tengan credenciales
QUEUE_MAX_AHEAD_DAYS = int(os.environ.get("QUEUE_MAX_AHEAD_DAYS") or 3)    # no programa más lejos que esto
QUEUE_MAX_PENDING = int(os.environ.get("QUEUE_MAX_PENDING") or 20)         # máximo de publicaciones en espera por red
QUEUE_CLIP_DAYS = int(os.environ.get("QUEUE_CLIP_DAYS") or 3)              # solo clips creados en los últimos N días
POSTER_SECONDS = int(os.environ.get("POSTER_SECONDS") or 30)               # cada cuánto revisa si hay algo que publicar
# Instagram Reels (Graph API): cuenta Business/Creator enlazada a tu página. El token de la página sirve.
IG_USER_ID = os.environ.get("IG_USER_ID", "").strip()
IG_TOKEN = (os.environ.get("IG_TOKEN") or os.environ.get("FB_PAGE_TOKEN") or "").strip()
# YouTube Shorts (Data API v3, OAuth): client id/secret de Google Cloud + refresh token de tu canal
YT_CLIENT_ID = os.environ.get("YT_CLIENT_ID", "").strip()
YT_CLIENT_SECRET = os.environ.get("YT_CLIENT_SECRET", "").strip()
YT_REFRESH_TOKEN = os.environ.get("YT_REFRESH_TOKEN", "").strip()
YT_PRIVACY = (os.environ.get("YT_PRIVACY") or "public").strip().lower()   # public | unlisted | private


# --- Parte 9: clips automáticos de lo mejor del momento (APAGADO por defecto) ---
DISCOVER = (os.environ.get("DISCOVER") or "0").strip().lower() in ("1", "true", "yes", "on")
DISCOVER_MINUTES = int(os.environ.get("DISCOVER_MINUTES") or 30)          # cada cuánto revisa cada fuente
DISCOVER_MAX_PER_DAY = int(os.environ.get("DISCOVER_MAX_PER_DAY") or 8)   # videos nuevos que puede procesar en 24 h (cuida tu cupo de IA)
DISCOVER_MAX_QUEUED = int(os.environ.get("DISCOVER_MAX_QUEUED") or 2)     # no encola más si ya hay tantos videos esperando
DISCOVER_INSPECT = int(os.environ.get("DISCOVER_INSPECT") or 6)           # máximo de videos que mira a fondo por revisión


# --- Buscador de clips virales (TikTok / Instagram Reels) ---
# TikTok se lee con yt-dlp desde perfiles públicos (tiktok:user) y links directos.
# Instagram necesita cookies (COOKIES_FILE) para sus reels; sin ellas se omite sin tumbar la búsqueda.
SEARCH_ACCOUNTS = int(os.environ.get("SEARCH_ACCOUNTS") or 12)              # máximo de perfiles por búsqueda
SEARCH_INSPECT = int(os.environ.get("SEARCH_INSPECT") or 8)                 # máximo de videos que se miran a fondo (miniatura/marca)
SEARCH_MIN_VIEWS = int(os.environ.get("SEARCH_MIN_VIEWS") or 10000)         # vistas mínimas para considerar un clip viral
SEARCH_MAX_AGE_HOURS = int(os.environ.get("SEARCH_MAX_AGE_HOURS") or 72)    # no buscar videos muy viejos
SEARCH_MIN_ENGAGEMENT = float(os.environ.get("SEARCH_MIN_ENGAGEMENT") or 1.5)  # likes / vistas en %
SEARCH_BRAND_FILTER = (os.environ.get("SEARCH_BRAND_FILTER") or "1").strip().lower() in ("1", "true", "yes", "on")
SEARCH_SEEDS = [s.strip() for s in (os.environ.get("SEARCH_SEEDS") or "").split(",") if s.strip()]  # perfiles por defecto


# --- Parte 10: Mi página (estadísticas y mejores horas aprendidas) y Facebook como fuente ---
STATS = _flag("STATS")                                            # leer los números de lo que publicas (solo en las redes con credenciales)
STATS_MINUTES = int(os.environ.get("STATS_MINUTES") or 60)           # cada cuánto lee los números de tus publicaciones
STATS_DAYS = int(os.environ.get("STATS_DAYS") or 30)                 # publicaciones de los últimos N días
STATS_BATCH = int(os.environ.get("STATS_BATCH") or 25)               # máximo de publicaciones que lee por vuelta
YT_API_KEY = os.environ.get("YT_API_KEY", "").strip()                # opcional: leer vistas de YouTube sin OAuth de lectura
LEARN_SLOTS = (os.environ.get("LEARN_SLOTS") or "1").strip().lower() in ("1", "true", "yes", "on")   # aprender tus mejores horas
LEARN_MIN_POSTS = int(os.environ.get("LEARN_MIN_POSTS") or 12)       # publicaciones con 24 h o más antes de fiarse de los datos
LEARN_MIN_PER_HOUR = int(os.environ.get("LEARN_MIN_PER_HOUR") or 2)  # publicaciones mínimas en una hora para que cuente
LEARN_SLOT_COUNT = int(os.environ.get("LEARN_SLOT_COUNT") or 3)      # cuántas horas por día
LEARN_GAP_HOURS = int(os.environ.get("LEARN_GAP_HOURS") or 2)        # separación mínima entre las horas elegidas
LEARN_EXPLORE = (os.environ.get("LEARN_EXPLORE") or "1").strip().lower() in ("1", "true", "yes", "on")  # 1 hora de prueba en un horario poco probado


# --- Parte 11: worker siempre activo (Docker) ---
RESTART_HOUR = int(os.environ.get("RESTART_HOUR") or 4)              # hora local (0-23) del reinicio diario que baja el yt-dlp nuevo; -1 = nunca
RECOVER_ON_START = (os.environ.get("RECOVER_ON_START") or "1").strip().lower() in ("1", "true", "yes", "on")   # al arrancar, retoma los trabajos que quedaron a medias

# ---- Parte 12: página Hacerlo viral (estudio de miniaturas y revisión)
STUDIO_SECONDS = int(os.environ.get("STUDIO_SECONDS") or 6)                  # cada cuánto atiende lo que pides desde la web (miniaturas, re-análisis)
VIRAL_REQUIRE_APPROVAL = (os.environ.get("VIRAL_REQUIRE_APPROVAL") or "0").strip().lower() in ("1", "true", "yes", "on")  # respaldo si no hay ajuste en la web
THUMB_BACKFILL_PER_TICK = int(os.environ.get("THUMB_BACKFILL_PER_TICK") or 2)  # miniaturas que hace por vuelta a clips que llegaron sin ella
THUMB_MAX_BYTES = 2_000_000                                                   # YouTube no acepta miniaturas de más de 2 MB

