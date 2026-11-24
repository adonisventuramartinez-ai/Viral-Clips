# Parte 9: clips automáticos de lo mejor del momento (Parte 3 del plan)

Copia encima de tu proyecto. Requiere Partes 7 y 8. Pruebas: `python test_parte9.py` (26) + las anteriores; la web compila.

## Antes de usarla
1. Supabase → SQL Editor: `supabase/migrations/0011_auto_clips.sql`.
2. Reconstruye el Docker y sube la web (nueva página **Clips automáticos**).
3. En `worker/.env`: `DISCOVER=1` (viene apagado). Agrega fuentes en la página.

## Cómo funciona
1. Tú agregas **fuentes**: un canal de YouTube (mira sus videos y sus directos ya terminados) o una **búsqueda** (ej. "La Casa de Alofoke 3", lo más nuevo).
2. Cada 30 min el worker (cuando está libre) mira lo nuevo y lee fecha, vistas y duración de cada video.
3. Descarta directos en curso, videos muy cortos/largos, viejos, con pocas vistas, o que ya tienes en tu biblioteca.
4. De los que sirven elige los que van **más fuertes = más vistas por hora**, y crea el trabajo de clips igual que si pegaras el link en Crear clips.
5. Cada clip pasa por el **área viral** (título, hashtags, miniatura, veredicto) y, con `AUTO_QUEUE=1`, entra a la **Cola** con su mejor hora. Todo el camino queda automático: encontrar → clip → viral → publicar.

## Frenos para que no se desboque
Máx. 4 videos nuevos por día (`DISCOVER_MAX_PER_DAY`), máx. 2 esperando a la vez, 4 clips por video, solo videos de las últimas 48 h, duración 3-120 min (ajustable por fuente). "Revisar ya" fuerza una revisión; "Pausar" la detiene.

## Límites (honestos)
- **"Lo mejor del momento" = lo más visto por hora entre las fuentes que tú eliges.** No lee tendencias de TikTok, Instagram ni Google Trends.
- Solo YouTube (canal o búsqueda). Facebook/Twitch como fuente: pendiente.
- **No lo probé contra YouTube real** (mi entorno no llega); probé la lógica con respuestas simuladas. Prueba con UNA fuente y mira "Lo que encontró".
- YouTube a veces pide cookies: usa las mismas `COOKIES_FILE` que ya tienes.
- **Derechos**: clipear canales de otros sin permiso puede darte strikes. Usa fuentes con permiso (como tu acuerdo con Alofoke) y revisa sus condiciones.
- Un video con pocas vistas hoy se vuelve a mirar después; los demás descartes quedan anotados y no se repiten.
