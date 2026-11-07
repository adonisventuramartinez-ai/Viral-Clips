# ClipForge

Convierte podcasts y videos en clips verticales virales con subtítulos.

- **Web** (Next.js → Vercel): crear trabajos, ver progreso y clips, descargar.
- **Base de datos y archivos** (Supabase): tablas, cola de trabajos y Storage.
- **Worker** (carpeta `worker/`, corre en tu PC con Docker): descarga, transcribe (Groq Whisper), elige momentos (Llama en Groq, gratis) y corta con ffmpeg.

## Puesta en marcha

1. **Supabase → SQL Editor:** ejecuta `supabase/migrations/0001_init.sql` y luego `0002_worker.sql`.
2. **Vercel → Settings → Environment Variables:** además de las de Supabase, agrega `APP_PASSWORD` (la contraseña que quieras). Luego *Redeploy*.
   Sin `APP_PASSWORD` la página responde 503 a propósito: las rutas /api usan la service role key y no deben quedar abiertas.
3. **Worker:** sigue `worker/README.md` (necesita `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` y `GROQ_API_KEY`).
4. Entra a tu página, pon la contraseña, ve a *Crear clips*, pega un link con un tramo corto y mira la *Biblioteca*.

## Estado por partes
- Parte 1 – interfaz y esquema: listo.
- Parte 2 – worker VOD: listo.
- Parte 3 – web conectada a datos reales + contraseña: listo.
- Parte 4 – modo En vivo (grabación + chat): pendiente.
- Parte 5 – "Pasar a narrado" y "Crear resumen": pendiente.
