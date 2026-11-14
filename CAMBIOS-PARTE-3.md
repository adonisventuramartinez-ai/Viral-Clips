# Parte 3: detección mejorada

Incluye todo lo de las Partes 1 y 2. Sin SQL nuevo. Pruebas: `python test_parte3.py` (60 pruebas).

## Qué hay nuevo

| Detector | Tipos que lo usan | Marca | Cómo funciona |
|---|---|---|---|
| Disparos y explosiones por audio | GTA 5 acción, Juegos | 💥 | Busca golpes de sonido: un disparo es seco y con agudos; una explosión es grave y se apaga en ~1 s. Un grito sostenido no cuenta. Hacen falta 3 disparos seguidos para contar un tiroteo. |
| Pantallas de GTA | GTA 5 acción (y GTA RP, con menos peso) | 📺 | Reconoce WASTED (letras rojas sobre imagen en blanco y negro), BUSTED (azules), MISSION PASSED (letras doradas) y estrellas de policía (esquina superior derecha) por color y posición. Exige 2 fotogramas seguidos (3 en estrellas). La IA recibe el detalle, p. ej. "(pantalla: WASTED)". |
| Discusiones | Reality | 🗯 | Marca ventanas de 8 s donde coinciden al menos 2 de 3: muchas palabras por segundo, volumen alto sostenido, chat explotando. |
| Clips repetidos | Reality | — | Compara lo que se dice en cada candidato con los ya elegidos y con tus clips de las últimas 48 h. Si se parecen (>= 55 %) deja el de mejor puntaje. |
| Verificación con imágenes | GTA, Juegos, Reality | 👁 | Para los 12 mejores candidatos saca 3 fotogramas y se los manda a un modelo con visión (Groq, Gemini o Claude). Menús, pantallas de carga o negro bajan el clip; si se ve la acción, sube un poco. |

Funciona en videos (Crear clips) y en En vivo, con una excepción: **la verificación con imágenes no corre en En vivo** (agregaría espera y gasto de cupo en cada revisión).

## Cosas que debes saber

- **No puedo probar con tus videos reales.** Probé con audio y fotogramas sintéticos y con videos generados con ffmpeg. Los umbrales (cuánto sube el volumen en un disparo, cuánto color tiene WASTED) están razonados, no calibrados con tu gameplay. Si ves falsos positivos o clips que se escapan, dime qué tipo de video fue y los ajusto.
- **Las pantallas de GTA se reconocen por color, no leyendo letras.** Una escena nocturna muy apagada con un objeto rojo grande podría confundirse con WASTED; por eso se exigen 2 fotogramas seguidos y la verificación con imágenes sirve de segunda opinión.
- **Discusiones sin saber quién habla.** Sin identificar voces (pyannote, Parte 5) no se puede contar cuántas personas hablan a la vez; se usa velocidad de habla + volumen + chat como aproximación.
- **Visión en Groq:** usa el modelo `meta-llama/llama-4-scout-17b-16e-instruct`. Si Groq lo cambia o tu cuenta no lo tiene, pon otro en `GROQ_VISION_MODEL` o deja `VERIFY_IMAGES=0`. Tiene su propio enfriamiento: un 429 en visión no deja sin texto a esa cuenta.
- **Tiempo:** el audio de 30 min se analiza en ~1 s y usa ~120 MB (se lee por bloques de 60 s). Las pantallas cuestan ~2 s por minuto de video 720p: un VOD de 4 h suma ~8 min.
- Cada detector se apaga en `.env` (`DETECT_AUDIO`, `DETECT_SCREEN`, `DETECT_ARGUMENT`, `DEDUPE`, `VERIFY_IMAGES`). Si uno falla, el trabajo sigue sin él.

## Archivos
Nuevos: `detect.py`, `vision.py`, `test_parte3.py`. Cambiados: `analyze.py`, `energy.py`, `profiles.py`, `llm.py`, `config.py`, `db.py`, `main.py`, `live.py`, `test_llm.py`, `.env.example`.
`test_llm.py` ahora ignora tu `worker/.env` real (antes fallaba si tenías `GROQ_MODEL` puesto).
