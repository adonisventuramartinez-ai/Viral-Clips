# Worker de ClipForge

Descarga/transcribe videos, elige momentos virales y produce clips verticales con ffmpeg.
Corre en tu PC con Docker y se conecta al mismo proyecto de Supabase que la web.

## Arranque
1. Instala Docker Desktop y déjalo corriendo.
2. Doble clic en `INICIAR-WORKER.bat` (equivale a `iniciar-worker.ps1`).
   La primera vez pide `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` y `GROQ_API_KEY`
   y los guarda en `worker/.env` (ignorado por git).
3. Espera el mensaje `Worker listo … esperando trabajos…` y deja la ventana abierta.

## Tipos de trabajo que atiende
- `download` → videos de YouTube/Twitch/Kick o links directos.
- `record` → directos (grabación + chat).
- `clip` → recorte/reescritura de un clip existente.
- `transform` → **Modo Transformar**: video externo (TikTok, IG, MP4) → clip 1080×1920 con voz, contexto, dramómetro, encuesta y logo. Ver `../TRANSFORMAR-CLIP.md`.
- `text_to_video` → **Crear con IA**: prompt + estilo → 4 escenas → video 1080×1920 de 60 s con subtítulos, logo y música. Ver `../CREAR-CON-IA.md`.

## Variables útiles (todas opcionales salvo las 3 del arranque)
| Variable | Default | Uso |
|---|---|---|
| `GROQ_API_KEY` / `GROQ_KEYS` / `groq_keys.txt` | — | IA (transcripción + análisis). Varias cuentas se rotan solas. |
| `CLIP_MAX_MB` | `44` | Tope de cada MP4 subido a Storage (Supabase rechaza ≥50 MB). |
| `CLIP_ENCODER` | `auto` | `auto`, `cpu`, `nvenc`, `qsv`, `amf`, `videotoolbox`. |
| `TRANSFORM_MAX_MB` | `45` | Tope del archivo de entrada en Modo Transformar (se aplica también a links). |
| `TRANSFORM_MAX_SECONDS` | `600` | Recorte de seguridad para videos largos. |
| `TRANSFORM_DEFAULT_SCORE` | `78` | Puntaje inicial del dramómetro. |
| `TRANSFORM_ALWAYS_ORIGINAL` | `1` | Fuerza el Modo Original aunque la petición diga lo contrario. |
| `TRANSFORM_INTRO` | `card` | `card` = tarjeta narrada antes del video; `cold` = arranca con el video. |
| `HF_TOKEN` | — | Obligatorio para `/crear-ia` (token de Hugging Face). |
| `HF_MODEL` | `damo-vilab/text-to-video-ms-1.7b` | Modelo de texto a video. |
| `IA_CLIPS` / `IA_CLIP_SECONDS` | `4` / `15` | Escenas y duración de cada una (4 × 15 s = 60 s). |
| `IA_TOTAL_SECONDS` | `60` | Duración final exacta. |
| `IA_MAX_RETRIES` / `IA_MAX_WAIT` | `4` / `25` | Reintentos por cold start y espera máxima. |
| `IA_MUSIC_URL` | — | Pista propia opcional; si no, se genera un pad con ffmpeg. |
| `REPLICATE_API_TOKEN` + `REPLICATE_VERSION` | — | Plan B de generación (REST, sin SDK). |
| `CAST_NAMES` | — | Nombres propios para que Whisper no los escriba mal. |

## Voz del Modo Original
Orden de preferencia: `edge-tts` (con timeout de 25 s) → `gTTS` → `espeak-ng` (offline,
incluido en la imagen Docker) → `pyttsx3` si está instalado. Si ningún proveedor responde,
la tarjeta se genera igual, sin audio; el trabajo no se pierde.

## Archivos que NO se suben a git
`.env`, `groq_keys.txt`, `*.cookies.txt`, `logs/`, `__pycache__/`, `work/`.
