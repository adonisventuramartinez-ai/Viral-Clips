"""Perfiles por tipo de contenido: qué busca la IA, cuánto contexto añadir antes/después y cuánto pesan las pistas.

Tipos: auto (general), podcast, entrevista, juego, directo.
"""

# bonus = puntos que suma cada pista si cae dentro del momento (🔊 volumen, 🎮 acción en pantalla, 💬 chat)
PROFILES = {
    "auto": {
        "label": "General", "kind": "un podcast/directo/video",
        "guide": "Busca polémica, humor, confesiones, historias con gancho, frases citables, reacciones fuertes y giros inesperados.",
        "preroll": 0.0, "tail": 0.4, "question": False, "action": False,
        "bonus": {"loud": 5, "motion": 4, "chat": 6},
        "keywords": [],
    },
    "podcast": {
        "label": "Podcast", "kind": "un podcast de conversación",
        "guide": ("Es un podcast de conversación. Busca opiniones fuertes o polémicas, confesiones, anécdotas con inicio-giro-final, "
                  "choques de posturas, datos sorprendentes, frases citables y humor. Evita saludos, presentaciones, publicidad, "
                  "relleno y temas que necesitan contexto previo."),
        "preroll": 0.0, "tail": 0.5, "question": True, "action": False,
        "bonus": {"loud": 3, "motion": 0, "chat": 6},
        "keywords": ["te voy a confesar", "nunca le dije", "polémica", "mentira", "secreto", "me pasó", "la verdad es",
                     "no lo vas a creer", "te juro", "me arrepiento"],
    },
    "entrevista": {
        "label": "Entrevista", "kind": "una entrevista (entrevistador y entrevistado)",
        "guide": ("Es una entrevista. Una respuesta casi nunca se entiende sin la pregunta: el clip debe EMPEZAR en la pregunta "
                  "(o en una frase que la resuma) y seguir con la respuesta completa. Busca revelaciones, confesiones, polémica, "
                  "emoción, respuestas inesperadas y frases memorables del entrevistado. Evita preguntas largas sin respuesta fuerte, "
                  "saludos y presentaciones."),
        "preroll": 0.0, "tail": 0.6, "question": True, "action": False,
        "bonus": {"loud": 2, "motion": 0, "chat": 5},
        "keywords": ["nunca había contado", "por primera vez", "te voy a decir la verdad", "me dolió", "fue difícil",
                     "no me arrepiento", "lo que nadie sabe", "polémica"],
    },
    "juego": {
        "label": "Juegos", "kind": "un directo o video de videojuegos",
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
    "directo": {
        "label": "Directo (charla)", "kind": "un directo de charla (just chatting)",
        "guide": ("Es un directo de charla. Busca reacciones, momentos graciosos, historias, interacción con el chat, polémicas "
                  "y cosas inesperadas. Evita tiempos muertos y lecturas largas del chat."),
        "preroll": 2.0, "tail": 0.8, "question": False, "action": False,
        "bonus": {"loud": 6, "motion": 3, "chat": 8},
        "keywords": ["no manches", "qué fuerte", "no lo puedo creer", "me muero", "jaja", "te lo juro"],
    },
}

KEYWORD_BONUS = 4   # una sola vez, aunque haya varias palabras


def get(name):
    """Devuelve el perfil pedido (o 'auto' si no existe), con su nombre en 'name'."""
    key = str(name or "auto").strip().lower()
    if key not in PROFILES:
        key = "auto"
    return {**PROFILES[key], "name": key}
