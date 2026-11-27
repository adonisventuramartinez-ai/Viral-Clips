# Parte 7: área "Hacerlo viral" (Parte 1 del plan)

Copia estas carpetas/archivos ENCIMA de tu proyecto (mismas rutas). Pruebas: `python test_parte7.py` (47) y todas las anteriores siguen pasando.

## Antes de usarla
1. Supabase → SQL Editor: ejecuta `supabase/migrations/0009_viral.sql`.
2. Reconstruye el Docker del worker (o reinicia el worker).
3. `npm run build` ya lo compilé aquí sin errores; súbelo a Vercel.

## Qué hace
Cada clip nuevo pasa por `worker/viral.py` ANTES de publicarse:
- **Mejor título**: la IA propone 5 y se puntúan por reglas (largo, curiosidad, pregunta, sin gritar, sin insultos). Gana el mejor; el original se guarda. En la tarjeta del clip: 🔥 Viral → "Usar" cambia el título.
- **Mejores hashtags**: mezcla de 5 (1 amplio #fyp + programa + tema), sin repetidos. Se meten también en el texto de TikTok/Reels/Shorts.
- **Miniatura**: texto corto de la IA sobre el mejor cuadro + **miniatura B** (otro cuadro, otro texto) para probar A/B.
- **Puntaje viral 0-100** = 50% lo que vio la IA al elegir el momento + 20% título + 20% arranque + 10% duración.
- **Veredicto**: ≥70 listo ✅ · 55-69 revísalo 👀 · <55 flojo ⛔. Si detecta insultos o acusaciones graves SIEMPRE pide revisión.
- **Mejor hora**: botón "🕐 Programar a la mejor hora" usa horas 12:30, 19:00 y 21:30 (hora RD, UTC-4), sin chocar con lo ya programado (mín. 90 min, máx. 6 por día).
- **Filtro**: la publicación automática en Facebook (`FB_AUTOPUBLISH`) solo sube clips con veredicto "listo".
- Clips en vivo o rehechos sin análisis se procesan solos cuando el worker está libre (sin miniatura).

## Ajustes opcionales (.env del worker)
`VIRAL=1`, `VIRAL_AUTO_TITLE=1`, `VIRAL_THUMB_AB=1`, `VIRAL_MIN_SCORE=70`, `VIRAL_REVIEW_SCORE=55`, `POST_SLOTS=12:30,19:00,21:30`, `POST_TZ_OFFSET=-4`, `POST_MIN_GAP_MIN=90`, `POST_MAX_PER_DAY=6`.
Para el botón de la web, pon las mismas `POST_SLOTS`/`POST_TZ_OFFSET` en Vercel si cambias los valores.

## Arreglo extra
`db.create_live_source`: la calidad del canal vigilado se perdía (quedó dentro de un comentario). Ya se respeta.

## Límites (honestos)
- Las horas por defecto son razonables, NO aprendidas de tu página. En la Parte 4 se calculan con tus estadísticas reales.
- El puntaje es una guía (IA + reglas), no una garantía de viralidad.
- La IA gasta 1 llamada extra por clip.
- No probé contra tu Supabase ni Facebook reales; probé la lógica, la miniatura con ffmpeg y la web (build).
- `test_framing.py` ya fallaba antes en mi entorno por depender de tu `.env`; no lo toqué.

## Lo que sigue
Parte 2: cola de publicación automática (Facebook + Instagram + YouTube Shorts). Parte 3: auto-clips de lo mejor del momento. Parte 4: área "Mi página" con estadísticas. Parte 5: Docker siempre activo.
