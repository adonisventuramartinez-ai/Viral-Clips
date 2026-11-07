# Worker de ClipForge

Toma los trabajos de la tabla `jobs` en Supabase y hace: descargar → transcribir → la IA elige momentos → ffmpeg corta a 9:16 con subtítulos → sube a Storage (`clips`) y guarda en la tabla `clips`.

## 1. Base de datos
Ejecuta `supabase/migrations/0002_worker.sql` en Supabase (SQL Editor).

## 2. Variables
Copia `.env.example` a `.env` y rellena `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` y `GROQ_API_KEY` (gratis en console.groq.com; sirve para transcribir y para elegir los clips). `ANTHROPIC_API_KEY` es opcional y de pago.

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
