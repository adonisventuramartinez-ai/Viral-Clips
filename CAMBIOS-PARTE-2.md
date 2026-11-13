# ClipForge · Parte 2: modo En vivo

## Qué cambia
1. **Reconexión automática**: si el enlace del stream caduca (YouTube lo hace tras unas horas) o se corta la red, el worker
   pide un enlace nuevo y sigue grabando en la misma fuente. Si el directo de verdad terminó (lo confirma 2 veces), cierra bien.
   Si el stream se congela sin dar trozos nuevos, también reconecta. Hasta `LIVE_RECONNECTS` intentos seguidos (por defecto 6).
2. **Chat en vivo** (YouTube y Twitch) con `chat-downloader`: cuando el chat explota se marca 💬 y sube el puntaje de ese momento.
   Si la librería falla o el directo no tiene chat, todo sigue sin esa pista.
3. **Pistas en vivo de volumen (🔊) y acción en pantalla (🎮)**: se calculan en cada trozo. En Juegos, si pasó algo y nadie hablaba,
   la IA recibe una línea `[acción sin voz]` para poder elegir esa jugada (igual que en Crear clips).
4. **Tipo de contenido en En vivo**: General, Juegos, Directo (charla), Podcast, Entrevista (+ nombre del juego).
   Usa los mismos perfiles de la Parte 1: prompt, margen antes/después, cortes en pausas y segunda pasada de pistas.
5. **Botón "✂ Clip ahora"**: corta los últimos ~45 s del directo. Sale cuando termina el trozo que se está grabando
   (con `SEGMENT_SECONDS=45` son menos de 1 minuto). Título, gancho, descripción y hashtags los pone la IA.
6. **Clips nuevos por revisión ajustable** (1 a 8; antes fijo en 2-3) y **barra de progreso** opcional.
7. **Canales automáticos**: en la página En vivo, lista de canales (YouTube `@canal`, Twitch…). El worker los revisa cada
   `WATCH_SECONDS` (120 s) y, cuando uno entra en vivo y el worker está libre, empieza a grabar solo con el tipo de contenido
   y formato que elegiste. No repite el mismo directo si lo paraste a mano (al "Activar" de nuevo, sí lo vuelve a tomar).
8. La página En vivo muestra reconexiones, mensajes de chat leídos y clips "en camino".

## Cómo desplegarlo
1. **Supabase > SQL Editor**: pega y ejecuta `supabase/migrations/0006_envivo.sql` (crea `live_commands` y `watch_channels`).
   Sin eso el directo funciona igual, pero no "Clip ahora" ni los canales automáticos.
2. Copia los archivos de este zip sobre tu proyecto (no trae `.git`, `worker/.env` ni cookies).
3. `git add -A`, mira `git status` (que NO aparezca `worker/.env` ni cookies), `git commit -m "parte 2: en vivo"`, `git push origin main`.
4. Worker: cierra y abre `INICIAR-WORKER.bat` (reconstruye la imagen e instala `chat-downloader`).
5. Opcional en `worker/.env`: `SEGMENT_SECONDS=30` (clips más rápido), `LIVE_CHAT=0` (sin chat), etc.

## Probado
- `python worker/test_live.py` (sin IA ni internet, con ffmpeg): picos de chat, hora real -> línea de tiempo con huecos de
  reconexión, picos de volumen y de imagen en un video de prueba, vigilante de canales, y un directo simulado completo
  (reconexión + pistas + 💬 + "Clip ahora" a mitad del directo a velocidad real + limpieza de la carpeta de trabajo).
- `python worker/test_calidad.py` (Parte 1) sigue pasando.
- Los `.ts`/`.tsx` nuevos pasan revisión de sintaxis. **No** pude compilar el proyecto Next.js completo: si Vercel marca un error de tipos, mándamelo.

## No probado con datos reales
- Conexión real a YouTube/Twitch: `yt-dlp`, `chat-downloader` y el re-pedido del enlace se probaron con piezas simuladas.
  Las ventanas de chat (10 s, mínimo 6 mensajes y el doble de lo normal) y los umbrales de acción están calibrados con datos
  de prueba: con un directo real quizá haya que ajustarlos.
- Un directo con muchas horas (el enlace caduca de verdad) y el flujo completo con tu Supabase.

## Límites a saber
- El worker graba **un directo a la vez**; los canales automáticos solo arrancan cuando está libre.
- Si el worker se apaga a media grabación, la fuente puede quedar como "grabando" hasta 3 h (después se re-encola sola);
  usa "Limpiar" en la Biblioteca si te estorba.
- Después de una reconexión hay un hueco sin video; un clip nunca mezcla las dos partes (se queda con la última).
- Clipear directos de otros creadores requiere su permiso.

## Sigue (Parte 3)
Quitar pausas y muletillas, quién habla (opcional), borrar la copia vieja de la web dentro de `worker/` y más pruebas.
