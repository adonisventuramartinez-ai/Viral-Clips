# Worker de ClipForge

Toma los trabajos de la tabla `jobs` en Supabase y hace: descargar → transcribir → la IA elige momentos → ffmpeg corta a 9:16 con subtítulos → sube a Storage (`clips`) y guarda en la tabla `clips`.

## 1. Base de datos
Ejecuta `supabase/migrations/0002_worker.sql` en Supabase (SQL Editor).

## 2. Variables
Copia `.env.example` a `.env` y rellena `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` y `GROQ_API_KEY` (gratis en console.groq.com; sirve para transcribir y para elegir los clips). Para que no se corte cuando se acabe el cupo, agrega más llaves gratis (Cerebras, Gemini, Mistral, OpenRouter, GitHub Models): ver `.env.example`.

## 2b. Cambio automático de IA
`llm.py` prueba los proveedores en orden. Si uno se queda sin cupo (429), tiene la llave mala o se cae, lo aparta y sigue con el siguiente; el trabajo no falla.
Al arrancar prueba cada llave y te dice cuál sirve. Si TODOS se quedan sin cupo espera hasta `LLM_MAX_WAIT` segundos y, si no vuelve ninguno, da un error claro.
La transcripción usa Whisper de Groq; si Groq se queda sin cupo, sigue con Whisper local (más lento, pero no se detiene).
Prueba sin gastar cupo: `python test_llm.py`.

## 2c. Calidad y encuadre de los clips
- Los clips salen a pantalla completa 1080x1920. El recorte se hace en la resolución ORIGINAL y luego se escala una sola vez (Lanczos + nitidez suave), por eso conviene bajar el video en **Máxima (4K)** en Crear clips.
- `CLIP_FRAMING=auto` detecta las caras y sigue a quien habla (con 2 personas lejos, paneo suave al que mueve la boca). Si no encuentra caras usa el centro (`CLIP_FOCUS_X`).
- Si la gente sale chica (plano abierto), hace **zoom** a la cara (`CLIP_FACE_SIZE`) hasta el límite de nitidez `CLIP_MAX_UPSCALE`. Con video 1080p casi no hay margen de zoom; con **4K** sí.
- El bitrate se calcula por clip para que nunca pase de ~44 MB (límite de 50 MB de Supabase gratis).
- Pruebas: `python test_framing.py`.

## 3. Correrlo
**En tu PC con Docker (recomendado para empezar):**
```
cd worker
docker build -t clipforge-worker .
docker run --rm --env-file .env clipforge-worker
```
**Sin Docker:** instala ffmpeg, luego
```
cd worker
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```
**En Railway / Fly / VPS:** despliega la carpeta `worker/` con el Dockerfile y define las mismas variables.

## Cosas a saber
- **YouTube bloquea IPs de servidores** ("Sign in to confirm you're not a bot"). En tu PC casi nunca pasa; en Railway/VPS sí. Solución: exporta un `cookies.txt` de tu navegador y pon su ruta en `COOKIES_FILE`.
- **Transcripción:** sin `GROQ_API_KEY` usa Whisper local en CPU (lento en servidores chicos). Con la llave de Groq va por la nube y es mucho más rápido. Para videos largos usa siempre el rango Desde/Hasta.
- **Tamaño:** cada clip se limita a ~6 Mbps para quedar bajo los 50 MB por archivo del plan gratis de Supabase Storage.
- **Dónde ver los clips (hasta la Parte 3):** Supabase → Storage → `clips`, y la tabla `clips`.
