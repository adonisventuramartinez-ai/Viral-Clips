# ClipForge · todo lo nuevo (versión completa)

## Encuadres
- **Dividido estilo stream**: tu cara grande arriba y el gameplay COMPLETO abajo (16:9), subtítulos en la unión. Cara automática o marcada a mano.
- **Dos personas** (nuevo): detecta a las dos solas; izquierda/arriba va arriba. Si no las ve, usa mitad izquierda y mitad derecha.
- Vertical y fondo difuminado siguen igual. Todos salen en 1080x1920.

## Lo nuevo de esta tanda
1. **Subtítulos personalizables** (Ajustes IA > Subtítulos): 5 estilos listos (clásico, neón, verde, fuego, minimalista) y colores, tamaño, borde, altura, mayúsculas y efecto pop a tu gusto.
2. **Texto gancho**: la IA escribe una frase corta que sale arriba los primeros ~3.5 s. Se activa/apaga y se ajusta el tiempo en Ajustes IA.
3. **Mejor detección de momentos**: marca los picos de volumen (🔊) y, en VODs de Twitch, cuando el chat explota (💬). La IA los usa de pista y esos momentos suben 6 puntos.
4. **Ajustar un clip** (Biblioteca > ✏️ Ajustar): cambia inicio/fin y/o el encuadre y el worker lo rehace (baja solo ese tramo). No sirve para clips de directos.
5. **Mis configuraciones guardadas** (Proyecto): guarda encuadre, duración, cantidad y calidad con un nombre. Y **varios links a la vez** (hasta 10, se procesan en cola con los mismos ajustes).

## Antes ya incluido
- Logo configurable (Ajustes IA): posición (6), tamaño, opacidad. Por defecto abajo al centro.
- Duración hasta 90 s, calidad hasta 4K, hasta 50 clips por video.
- En vivo respeta el encuadre; página /clipeadores; setup_completo.sql con la migración 0004.
- Biblioteca: buscador, filtro por score, público/privado, copiar título + hashtags, duración en segundos.
- /api/jobs valida todo; la IA busca clips más cerca de la duración pedida.

## Para desplegar
1. Supabase > SQL Editor: ejecuta supabase/migrations/0004_comunidad.sql (si no lo hiciste). No hay SQL nuevo en esta tanda.
2. git add -A && git commit -m "mejoras" && git push origin main  (espera el deploy de Vercel)
3. Worker: docker build --no-cache -t clipforge-worker .  y arráncalo de nuevo.
4. Copia tu worker/.env desde tu PC (este zip va sin él).
5. Entra a Ajustes IA: sube tu logo y elige tu estilo de subtítulos.

## Qué NO se probó con datos reales
- El chat de Twitch (💬) depende de que yt-dlp pueda bajarlo; si no puede, se ignora y todo sigue igual.
- "Ajustar" y los Ajustes de logo/subtítulos necesitan tu Supabase y tu worker; el render sí se probó con ffmpeg.
- Fuente de los subtítulos: DejaVu Sans Bold (la que trae el Docker).

# Quinta tanda
- Dividido con 3 tamaños (Proyecto, En vivo y Ajustar): "Cara grande" (cara arriba 68% + gameplay completo abajo), "Equilibrado" (mitad y mitad, el gameplay se recorta un poco de los lados) y "Juego grande" (gameplay ~60%). Por defecto el botón Dividido usa Equilibrado.
- Este zip ya NO trae la carpeta .git (el anterior la traía y por eso Git te daba conflictos).
