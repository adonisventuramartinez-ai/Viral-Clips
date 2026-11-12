# ClipForge · Parte 1: calidad de los clips (podcast, entrevista, juegos)

## Qué cambia
1. **Tipo de contenido** (Crear clips): General, Podcast, Entrevista, Juegos y Directo. Cada uno tiene su propio prompt para la IA,
   su propio peso de pistas y su propio margen antes/después de la jugada. En Juegos puedes poner el nombre del juego.
2. **Cortes en pausas y finales de frase**: el clip ya no termina a media frase (usa los tiempos de cada palabra).
3. **Entrevistas y podcasts**: si justo antes del momento hay una pregunta, el clip empieza en la pregunta.
4. **Segunda pasada de la IA**: después de juntar candidatos, la IA los ve todos juntos y los re-puntúa (mezcla 40% / 60%).
   Si falla o no hay cupo, se queda con los puntajes originales. Se apaga con `RERANK=0`.
5. **Juegos sin voz**: detecta cambios bruscos de imagen (🎮) con ffmpeg y los suma al volumen (🔊) y al chat (💬).
   Donde hubo acción pero nadie hablaba, la IA recibe una línea `[acción sin voz]` para poder elegir esa jugada.
   En Juegos el clip empieza 6 s antes del pico.
6. **Palabras clave** por tipo ("clutch", "te voy a confesar"...): +4 puntos una sola vez.
7. **Descripción y hashtags** escritos por la IA para cada clip. En la Biblioteca hay botones **TikTok / Shorts / Reels**
   que copian el texto listo para cada red.
8. **Barra de progreso** opcional abajo del clip.

## Cómo desplegarlo
1. Supabase > SQL Editor: pega `supabase/migrations/0005_calidad.sql` y ejecuta (si no lo haces, todo funciona igual
   pero sin descripción/hashtags y sin guardar las opciones de la fuente).
2. Copia los archivos de este zip sobre tu proyecto (este zip NO trae `.git`, `worker/.env` ni cookies: no los pises).
3. `git add -A && git commit -m "parte 1: calidad" && git push origin main` y espera el deploy de Vercel.
4. Worker: cierra y abre `INICIAR-WORKER.bat` (reconstruye la imagen).
5. Opcional en `worker/.env`: `RERANK=0` o `SNAP_CUTS=0` para apagar alguna mejora.

## Probado
- `python worker/test_calidad.py` (10 pruebas, sin gastar IA): cortes, pregunta, preroll, bonus, acción sin voz, segunda pasada, prompts.
- Detección de acción con un video de prueba: marcó justo los segundos de la ráfaga.
- Render con barra de progreso y con logo en ffmpeg (sale 1080x1920, se ve la barra).
- El worker importa bien y `save_clip` envía descripción/hashtags.
- Los `.ts` pasan revisión de sintaxis. **No** pude compilar el proyecto Next.js completo aquí: si Vercel marca un error de tipos, mándamelo.

## No probado con datos reales
- Las llamadas reales a la IA (solo con respuestas simuladas) y el flujo completo con tu Supabase.
- La detección de acción en gameplay real: los umbrales están calibrados con un video de prueba. Si marca de más o de menos, avísame.

## Pendiente (siguientes partes)
- Parte 2: modo en vivo (reconexión, chat de YouTube, botón "Clip ahora", canales automáticos, pistas en vivo).
- Parte 3: quitar pausas/muletillas, quién habla (opcional), limpiar la copia vieja de la web dentro de `worker/`.
