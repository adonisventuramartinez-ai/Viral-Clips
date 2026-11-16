# Parte 10: Conectar cuentas, Mi página (estadísticas + mejores horas aprendidas) y Facebook como fuente (Parte 4 del plan)

Copia encima de tu proyecto (después de las Partes 7, 8 y 9). Pruebas: `python test_parte10.py` (86) + las anteriores; la web tiene una página nueva, **Mi página**.

## Antes de usarla
1. Supabase → SQL Editor: `0012_mi_pagina.sql` (estadísticas, horas aprendidas, Facebook como fuente) y `0013_conexiones.sql` (llaves de tus cuentas).
2. Reconstruye el Docker del worker y sube la web a Vercel.
3. Nada más: viene encendida (`STATS=1`, `LEARN_SLOTS=1`) y solo actúa en las redes con credenciales en `worker/.env`.

## Conectar cuentas (web: menú "Conectar cuentas")
Una tarjeta por red (Facebook, Instagram, YouTube Shorts): pegas las llaves, das «Conectar» y el worker las toma en ~2 min **sin reiniciar**. Cada tarjeta trae la guía «¿De dónde saco esto?» y muestra si el worker ya la está usando.
- Facebook: ID de la página + token de la página. Instagram: ID de la cuenta (+ token propio opcional; si no, usa el de Facebook). YouTube: Client ID, Client secret, Refresh token (+ API key opcional para estadísticas).
- Las llaves van a tu Supabase (tabla `connections`, solo legible con la service role). La web nunca las devuelve completas (solo `••••1234`). Un campo vacío no borra el guardado. Lo guardado en la web manda sobre `worker/.env`.
- Es pegar llaves, **no** un botón «Iniciar sesión con Facebook»: ese botón requiere una app de Meta/Google aprobada por ellos. Conseguir el token sigue siendo el trámite de Meta/Google; la guía explica los pasos.
- «Quitar» borra las llaves guardadas; el worker deja de usarlas al reiniciarlo.

## Mi página (web: menú "Mi página")
- Totales de los últimos 7/30/90 días: publicaciones, vistas, likes, comentarios (y compartidos en Instagram).
- Por red: publicaciones, vistas, promedio por publicación y **seguidores** con el cambio de 7 días.
- Los 10 clips que mejor te han funcionado.
- **Tus mejores horas**: barras por hora comparadas con tu promedio (1.00× = promedio), por red o de todas.
- Lo próximo en la cola.

## Cómo se leen los números
Un hilo propio del worker (así nunca retrasa una publicación) lee cada `STATS_MINUTES` (60) lo recién publicado, y cada 12 h lo que tiene más de 3 días. Lee lo publicado por la cola y lo programado a mano en Facebook.
- Facebook: vistas, likes y comentarios del video/Reel (Graph API, con `FB_PAGE_TOKEN`).
- Instagram: vistas, likes, comentarios y compartidos (`IG_TOKEN`).
- YouTube: vistas, likes y comentarios. **Ojo**: el token con el que subes (`youtube.upload`) normalmente NO deja leer estadísticas. Pon `YT_API_KEY` (una llave de API de Google Cloud, sirve para videos públicos) o vuelve a autorizar con el permiso `youtube.readonly`.
- Si una lectura falla, se guarda el motivo y NO se borran los números anteriores.

## Cómo se aprenden las horas
1. Solo cuentan publicaciones con 24 h o más (antes los números siguen creciendo).
2. Cada una se compara con el promedio de SU red (así YouTube con muchas vistas no tapa a Facebook).
3. Se agrupan por hora del día. Una hora con pocas publicaciones se acerca al promedio, para que un solo golpe de suerte no gane.
4. Se eligen `LEARN_SLOT_COUNT` (3) horas, separadas al menos `LEARN_GAP_HOURS` (2) h. Una es **de prueba** (la hora de día menos probada) para que el sistema siga descubriendo; si rinde, pasa a ser una de las mejores.
5. Con menos de `LEARN_MIN_POSTS` (12) publicaciones no cambia nada: se usan tus `POST_SLOTS`.
6. La cola automática usa las horas de cada red (si una red no tiene datos propios, las de "todas"). El botón "🕐 Programar a la mejor hora" de la tarjeta del clip también las usa.

## Facebook como fuente (Clips automáticos → "Página de Facebook")
Pega el link de la página (`https://www.facebook.com/NombreDePagina`), su nombre o su id. Funciona igual que YouTube: cada 30 min mira los videos nuevos, descarta directos en curso, cortos, largos, viejos y repetidos, elige los que van más fuertes y crea el trabajo de clips.
- Se lista con la Graph API y `FB_PAGE_TOKEN`. **Con TUS páginas funciona. Con páginas de otras personas solo si tu app de Meta tiene el permiso "Page Public Content Access"** (hay que pedirlo en la revisión de Meta); si no, la fuente muestra el motivo en "Revisada…".
- Facebook a veces no da `views`: en ese caso usa las reacciones como medida aproximada para ordenar.
- La descarga la hace yt-dlp con el link del video. Los videos públicos suelen bajar; los de páginas con restricciones pueden pedir cookies de Facebook (`COOKIES_FILE` es de YouTube y no sirve para eso).
- Derechos: igual que en YouTube, usa páginas propias o con permiso.

## Límites (honestos)
- **No lo probé contra Facebook, Instagram ni YouTube reales** (mi entorno no llega). Probé la lógica y la lectura con respuestas simuladas; los nombres de campos y métricas de la Graph API cambian con las versiones. Mira la primera vez que corra: si una métrica no viene, la publicación aparece con 0 vistas y el motivo en la consola.
- **La web no pude compilarla completa** (sin `node_modules` ni red aquí): revisé los tipos con módulos simulados. Si `next build` marca algo, pásame el error.
- Aprender horas necesita volumen: con 3 publicaciones al día tardas ~4 días en llegar a 12. Las horas son una guía, no una garantía; el puntaje de cada hora depende de qué clips cayeron en ella.
- La hora mostrada es la hora real en que salió la publicación (redondeada a 15 min), no la programada.

## Archivos
Nuevos: `worker/insights.py`, `worker/connections.py`, `app/api/conexiones/route.ts`, `app/conectar/page.tsx`, `supabase/migrations/0013_conexiones.sql`, `worker/test_parte10.py`, `app/api/pagina/route.ts`, `app/mi-pagina/page.tsx`, `supabase/migrations/0012_mi_pagina.sql`.
Cambiados: `worker/config.py`, `db.py`, `discover.py`, `autoqueue.py`, `poster.py`, `main.py`, `.env.example`, `components/Sidebar.tsx`, `lib/slots.ts`, `app/api/clips/[id]/route.ts`, `app/api/feeds/route.ts`, `app/auto/page.tsx`, `supabase/setup_completo.sql`.
