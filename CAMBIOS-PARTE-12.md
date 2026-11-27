# Parte 12: página «Hacerlo viral» (estudio de miniaturas y revisión de cada clip)

Copia encima de tu proyecto (después de la Parte 11). Pruebas: `python test_parte12.py` (64) + las anteriores.

## Antes de usarla
1. Supabase → SQL Editor: ejecuta `0014_viral_estudio.sql`.
2. Reconstruye el Docker del worker (`INICIAR-SIEMPRE.bat`) y sube la web a Vercel.
3. En el menú nuevo **Hacerlo viral**.

## Qué es
Un solo lugar por donde pasa cada clip antes de salir. Cada clip que el worker guarda ya se analizaba (Parte 7); ahora lo ves y lo trabajas:

- **Pestañas**: Por revisar · Listos · Aprobados · Descartados, con conteo.
- **Miniaturas A y B** lado a lado. Por cada una: cambias el **texto**, el **estilo** (amarillo, rojo, blanco, al centro) y el **cuadro**: pausas el video donde quieras y tocas «📍 Usar el cuadro del video». «🔄 Rehacer» la crea de nuevo en segundos. Marcas cuál **se publica** (A o B).
- **Título**: lo editas con el puntaje cambiando en vivo mientras escribes, ves las 5 opciones de la IA («Usar») y puedes pedir otras («🔄 Pedir otros títulos a la IA»).
- **Hashtags y descripción**: editables. Al guardar, la Cola y los textos de TikTok/Reels/Shorts usan lo nuevo.
- **Por qué tiene ese puntaje**: cuánto aporta el momento, el título, el arranque y la duración, y una lista «✅/🟡/❌» de lo que falta antes de publicar.
- **Acciones**: ✅ Aprobar y mandar a la cola · 🕐 Programar en Facebook a la mejor hora · 🗑 Descartar · ↩ Volver a revisar. «Aprobar todos los listos» en bloque (los que traen riesgo no entran: los decides tú).
- **Aprobar yo cada clip** (interruptor arriba): encendido, a la Cola y a la publicación automática de Facebook solo llegan los clips **aprobados** aquí. Apagado (como venía), entran solos los «listos» (70+).

## La miniatura ahora SÍ se usa al publicar
Antes se hacía pero nunca se subía a ninguna red.
- **Instagram**: se manda como portada del Reel (`cover_url`). Si Instagram la rechaza, el Reel sale igual sin portada propia.
- **YouTube**: se sube después del video con `thumbnails.set`. Si falla, el video ya está publicado y no se toca. YouTube solo acepta miniaturas propias en canales **verificados por teléfono** y de máx. 2 MB.
- **Facebook Reels**: no la usa. No encontré un campo de miniatura en el flujo de Reels de la API que usa el worker; ahí sale la que Facebook escoja.

## Cómo funciona por dentro
- La web no hace el trabajo pesado: deja un pedido en `clips.viral_req` y un hilo nuevo del worker (`worker/studio.py`, cada 6 s, aparte del render y de los directos) baja el clip terminado, saca el cuadro, pone el texto, lo sube y borra la miniatura vieja. Si falla, la web muestra el motivo.
- Cada miniatura nueva tiene ruta nueva, así ningún navegador ni red ve la vieja en caché.
- Clips que llegan sin miniatura (en vivo, rehechos) la reciben solos (hasta 2 por vuelta; si falla una vez no se reintenta en bucle).
- Cuando usas «Ajustar» en la Biblioteca (otro inicio/fin), la miniatura se rehace sola porque el video cambió.
- «Pedir otros títulos» NO cambia tu título ni tus hashtags: solo renueva las sugerencias. Un clip aprobado sigue aprobado.

## Límites (honestos)
- **No lo probé contra Instagram ni YouTube reales**: la portada de IG y `thumbnails.set` están probados con respuestas simuladas. Haz la primera prueba con UN clip y mira la consola del worker. Si YouTube la rechaza, el motivo sale ahí.
- **No pude compilar la web completa** (sin `node_modules` ni red aquí). Revisé los tipos de lo nuevo con módulos simulados y comprobé que el puntaje del título en la web da igual que el de Python (8 casos). Si `next build` marca algo, pásame el error.
- Las miniaturas se hacen con el worker prendido; si está apagado el pedido espera.
- Para YouTube/Instagram la miniatura es 9:16 (1080×1920). En YouTube Shorts la miniatura propia puede no verse en el feed de Shorts; sí en otras vistas.
- El puntaje es una guía (IA + reglas), no garantiza que se haga viral. El mínimo «70» de la lista de la web es el valor por defecto de `VIRAL_MIN_SCORE`; si lo cambias en el worker, el texto de la lista no se entera.
- Con el interruptor de aprobación encendido, lo que ya estaba «listo» antes deja de entrar solo a la Cola hasta que lo apruebes.

## Archivos
Nuevos: `worker/studio.py`, `worker/test_parte12.py`, `app/viral/page.tsx`, `app/api/viral/route.ts`, `lib/viral.ts`, `supabase/migrations/0014_viral_estudio.sql`.
Cambiados: `worker/thumb.py` (estilos, cuadro exacto), `worker/db.py`, `worker/main.py`, `worker/poster.py`, `worker/publisher_ig.py`, `worker/publisher_yt.py`, `worker/rerender.py`, `worker/config.py`, `worker/.env.example`, `lib/types.ts`, `lib/clips.ts`, `components/Sidebar.tsx`, `components/ClipCard.tsx`, `supabase/setup_completo.sql`.
