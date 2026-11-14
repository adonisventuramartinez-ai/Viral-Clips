"""Perfiles por tipo de contenido: qué busca la IA, cuánto contexto añadir antes/después y cuánto pesan las pistas.

Tipos: auto (general), reality (La Casa de Alofoke), podcast, entrevista, juego, gta (acción), gta_rp (roleplay), directo.

"ideal" = largo ideal del clip en segundos para ese tipo (se usa cuando en la web eliges "Automática").
"""
import re
import unicodedata

import config


# bonus = puntos que suma cada pista si cae dentro del momento (🔊 volumen, 🎮 acción en pantalla, 💬 chat)
PROFILES = {
    "auto": {
        "label": "General", "ideal": 45, "kind": "un podcast/directo/video",
        "guide": "Busca polémica, humor, confesiones, historias con gancho, frases citables, reacciones fuertes y giros inesperados.",
        "preroll": 0.0, "tail": 0.4, "question": False, "action": False,
        "bonus": {"loud": 5, "motion": 4, "chat": 6},
        "keywords": [],
    },
    "podcast": {
        "label": "Podcast", "ideal": 75, "kind": "un podcast de conversación",
        "guide": ("Es un podcast de conversación. Busca opiniones fuertes o polémicas, confesiones, anécdotas con inicio-giro-final, "
                  "choques de posturas, datos sorprendentes, frases citables y humor. Evita saludos, presentaciones, publicidad, "
                  "relleno y temas que necesitan contexto previo."),
        "preroll": 0.0, "tail": 0.5, "question": True, "action": False,
        "bonus": {"loud": 3, "motion": 0, "chat": 6},
        "keywords": ["te voy a confesar", "nunca le dije", "polémica", "mentira", "secreto", "me pasó", "la verdad es",
                     "no lo vas a creer", "te juro", "me arrepiento"],
    },
    "entrevista": {
        "label": "Entrevista", "ideal": 75, "kind": "una entrevista (entrevistador y entrevistado)",
        "guide": ("Es una entrevista. Una respuesta casi nunca se entiende sin la pregunta: el clip debe EMPEZAR en la pregunta "
                  "(o en una frase que la resuma) y seguir con la respuesta completa. Busca revelaciones, confesiones, polémica, "
                  "emoción, respuestas inesperadas y frases memorables del entrevistado. Evita preguntas largas sin respuesta fuerte, "
                  "saludos y presentaciones."),
        "preroll": 0.0, "tail": 0.6, "question": True, "action": False,
        "bonus": {"loud": 2, "motion": 0, "chat": 5},
        "keywords": ["nunca había contado", "por primera vez", "te voy a decir la verdad", "me dolió", "fue difícil",
                     "no me arrepiento", "lo que nadie sabe", "polémica"],
    },
    "reality": {
        "label": "Reality (Casa de Alofoke)", "ideal": 45,
        "kind": "un reality show 24/7 en vivo (La Casa de Alofoke 3) con varios participantes conviviendo",
        "guide": (
            "Es un reality de convivencia 24/7 en República Dominicana. Lo que se vuelve viral es el DRAMA y la emoción: peleas y "
            "discusiones (varias personas hablando a la vez, gritos), traiciones, chismes y confrontaciones ('dímelo en mi cara'), "
            "romances y celos, confesiones, reconciliaciones, nominaciones y eliminaciones, y reacciones exageradas o muy graciosas. "
            "El español es dominicano (vaina, tíguere, klk, dime a ver…). Importa QUIÉN dice qué: si sabes el nombre de quien habla "
            "o de a quien se refieren, úsalo en el título y el gancho. El clip debe tener tensión: empieza justo antes del conflicto "
            "(la frase que lo enciende) y termina en el punto más fuerte o en la reacción. Evita tiempos muertos, rutinas de comida o limpieza, "
            "conversaciones sin conflicto y charla que necesita contexto de días anteriores."),
        "preroll": 3.0, "tail": 1.5, "question": False, "action": False,
        "bonus": {"loud": 8, "motion": 0, "chat": 9},
        "keywords": ["pelea", "pelear", "discusión", "discutir", "traición", "traicionó", "traidor", "traidora", "dime a ver",
                     "mentiroso", "mentirosa", "falso", "falsa", "hipócrita", "chisme", "te lo dije", "en mi cara", "respétame",
                     "no me grites", "me tienes harto", "me tienes harta", "habla claro", "cállate", "lárgate",
                     "nominado", "nominada", "nominación", "eliminado", "eliminada", "expulsado", "expulsión", "me engañaste",
                     "me traicionaste", "celos", "infiel", "te quiero", "te extraño", "me dolió", "llorando", "perdóname",
                     "se acabó", "ya no más", "qué vergüenza", "qué descaro", "sinvergüenza", "atrevida", "atrevido"],
        "cast": True,
    },
    "juego": {
        "label": "Juegos", "ideal": 30, "kind": "un directo o video de videojuegos",
        "guide": ("Es contenido de videojuegos. Lo mejor suele ser la ACCIÓN: jugadas épicas, victorias de último segundo, clutch, "
                  "fails graciosos, sustos, rage, reacciones exageradas del streamer y bugs. Pueden ser momentos con poca o ninguna voz: "
                  "las marcas 🎮 (cambio brusco de imagen), 🔊 (pico de volumen) y las líneas [acción sin voz] indican que pasó algo en pantalla. "
                  "Empieza unos segundos ANTES de la jugada para que se entienda el contexto."),
        "preroll": 6.0, "tail": 2.5, "question": False, "action": True,
        "bonus": {"loud": 7, "motion": 8, "chat": 8},
        "keywords": ["clutch", "ace", "pentakill", "no way", "no puede ser", "qué locura", "increíble", "imposible", "wtf",
                     "insane", "let's go", "lets go", "vamos", "nooo", "mira eso", "last second", "gané", "ganamos", "victoria",
                     "headshot", "1v", "booyah"],
    },
    "gta": {
        "label": "GTA 5 · acción", "ideal": 25, "game": "GTA 5",
        "kind": "un directo o video de GTA 5 (Grand Theft Auto V) con personas jugando",
        "guide": (
            "Es GTA 5 con personas jugando, modo ACCIÓN (online, freeroam, misiones, atracos). Lo viral: tiroteos y persecuciones "
            "policiales (estrellas de búsqueda), explosiones, choques y saltos imposibles, kills o escapes de último segundo, "
            "fails graciosos y físicas locas, traiciones entre amigos, WASTED/BUSTED, y las reacciones exageradas de los jugadores "
            "(gritos, risas, 'no puede ser'). Muchos momentos tienen poca voz: las marcas 🎮 (cambio brusco de imagen), 🔊 (pico de volumen) "
            "y las líneas [acción sin voz] indican que pasó algo. Ojo: en GTA la cámara se mueve siempre, así que un cambio de imagen solo "
            "NO es acción; dale más peso al volumen y a lo que dicen. El clip empieza unos segundos ANTES de la jugada para que se entienda "
            "y termina en el desenlace o la reacción. Corto y directo: ideal 15 a 30 segundos."),
        "preroll": 5.0, "tail": 2.5, "question": False, "action": True,
        "bonus": {"loud": 9, "motion": 4, "chat": 8},
        "keywords": ["wasted", "busted", "mission passed", "me mataron", "me mató", "me explotó", "explotó", "explosión", "choque",
                     "persecución", "policía", "los pacos", "la policía", "cinco estrellas", "5 estrellas", "tanque", "avión",
                     "helicóptero", "helicoptero", "headshot", "no puede ser", "qué locura", "increíble", "imposible", "wtf",
                     "nooo", "vamos", "let's go", "lets go", "mira eso", "me tumbó", "atraco", "heist"],
    },
    "gta_rp": {
        "label": "GTA RP (roleplay)", "ideal": 40, "game": "GTA 5 RP",
        "kind": "un directo o video de GTA 5 Roleplay (servidor RP) con personas interpretando personajes",
        "guide": (
            "Es GTA 5 ROLEPLAY: lo importante es el DIÁLOGO y la actuación, no la acción. Lo viral: escenas graciosas o tensas entre "
            "personajes, interrogatorios y negociaciones con la policía, atracos y secuestros con diálogo, improvisaciones cómicas, "
            "discusiones y traiciones entre personajes, personajes ridículos o muy bien actuados, momentos donde alguien rompe el "
            "personaje de risa, y giros inesperados. Elige escenas completas con inicio, conflicto y remate (una broma que cierra). "
            "Las explosiones o persecuciones solo cuentan si vienen con diálogo fuerte. Evita conducir en silencio, menús, "
            "esperas, y charla técnica del servidor o de reglas. Ideal 30 a 50 segundos."),
        "preroll": 2.0, "tail": 1.5, "question": False, "action": False,
        "bonus": {"loud": 7, "motion": 0, "chat": 9},
        "keywords": ["manos arriba", "alto ahí", "quieto", "al suelo", "te voy a arrestar", "estás detenido", "tengo derecho",
                     "abogado", "rehén", "rehen", "dame todo", "esto es un atraco", "te voy a matar", "no me dispares",
                     "no dispares", "fail rp", "rompí el rol", "no rolees", "nuevo en la ciudad", "te lo juro oficial",
                     "señor oficial", "oficial", "me secuestraron", "mi personaje", "jajaja", "me muero",
                     "no lo puedo creer", "qué vergüenza", "traición", "me traicionó", "mentira"],
    },
    "directo": {
        "label": "Directo (charla)", "ideal": 45, "kind": "un directo de charla (just chatting)",
        "guide": ("Es un directo de charla. Busca reacciones, momentos graciosos, historias, interacción con el chat, polémicas "
                  "y cosas inesperadas. Evita tiempos muertos y lecturas largas del chat."),
        "preroll": 2.0, "tail": 0.8, "question": False, "action": False,
        "bonus": {"loud": 6, "motion": 3, "chat": 8},
        "keywords": ["no manches", "qué fuerte", "no lo puedo creer", "me muero", "jaja", "te lo juro"],
    },
}

KEYWORD_BONUS = 4   # una sola vez, aunque haya varias palabras

# Nombres de tipo que la web y el worker aceptan (la web los valida con la misma lista)
TYPES = ["auto", "reality", "podcast", "entrevista", "juego", "gta", "gta_rp", "directo"]


def norm(text):
    """Minúsculas y sin acentos: 'Traición' y 'traicion' cuentan igual (Whisper no siempre pone tildes)."""
    t = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def resolve_secs(requested, prof, lo=15, hi=120):
    """Largo del clip: si la web mandó 0 / 'auto' / nada, usa el ideal del tipo; si mandó un número, lo respeta (entre lo y hi)."""
    try:
        n = int(float(requested))
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        n = int(prof.get("ideal", 45))
    return max(lo, min(hi, n))


def get(name):
    """Devuelve el perfil pedido (o 'auto' si no existe), con su nombre en 'name'."""
    key = str(name or "auto").strip().lower()
    if key not in PROFILES:
        key = "auto"
    prof = {**PROFILES[key], "name": key}
    if prof.get("cast") and config.CAST_NAMES:
        prof["guide"] += (" Elenco conocido (úsalo para saber quién es quién y escribe los nombres bien): "
                          + ", ".join(config.CAST_NAMES) + ".")
    return prof
