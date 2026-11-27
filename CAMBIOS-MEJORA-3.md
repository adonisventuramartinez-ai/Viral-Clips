# Mejora 3: paquete de publicación, miniatura, ganchos A/B y programación

Aplícala **después** de las Mejoras 1 y 2 (copia las carpetas encima del proyecto). **Lleva SQL nuevo.**

## Pasos
1. **Supabase → SQL Editor:** pega y ejecuta `supabase/migrations/0007_publicacion.sql` (o todo `setup_completo.sql`; se puede correr varias veces). Sin esto los clips se siguen creando, pero sin paquete, miniatura ni programación (el worker avisa en consola).
2. En la carpeta `worker`: `pip install Pillow` (o reconstruye el Docker; ya está en `requirements.txt`).
3. `npm run build` antes de subir la web.

## Qué hace (clips nuevos)
- **Paquete por red** (`worker/packager.py`): una llamada de IA por clip escribe el texto de **TikTok** (gancho primero, ≤130 car., 3-5 hashtags con #fyp), **Reels/Facebook** (2 líneas + pregunta para comentar), **Shorts** (título ≤70 car. + descripción + #Shorts), 3 ganchos alternativos y un comentario para fijar. Si la IA no responde usa una plantilla, así que nunca queda vacío. Los botones 📋 TikTok / Shorts / Reels de la Biblioteca ya copian este texto. Se apaga con `PACK=0`.
- **Miniatura automática** (`worker/thumb.py`): elige entre 10 cuadros el más nítido, con cara bien ubicada y buena luz; pone el título en mayúsculas con la palabra más larga en amarillo, en la zona segura, sobre un degradado que tapa los subtítulos del cuadro. Sale como poster del video y botón 🖼 Miniatura. Se apaga con `THUMBS=0`.
- **Ganchos A/B**: botón 🎣 Ganchos muestra las 3 alternativas; "Usar" rehace el clip con ese texto arriba para que publiques las dos versiones y compares.
- **Programación en Facebook** (`worker/scheduler.py`): en cada clip, 🗓 Programar con fecha y hora; el worker lo publica en tu página cuando llega (revisa cada 60 s, `SCHEDULE_CHECK_SECONDS`). Requiere `FB_PAGE_ID` y `FB_PAGE_TOKEN` en `worker/.env`. El clip se marca antes de publicar: si el worker se cae a mitad, **no se publica dos veces** (queda en "error" con el motivo y lo reprogramas). Para TikTok y Shorts no hay API conectada: se copia el texto y se sube a mano.

## Pruebas
`python test_mejora3.py` (paquete, miniatura con ffmpeg y Pillow, programación con base de datos y Facebook simulados). Todas las pruebas anteriores siguen pasando.

## Límites
- **Facebook sin probar con tu página real**: la publicación usa el mismo código de Reels que ya tenías (`publisher.py`), pero la programación no la pude ejecutar contra la API de Meta. Prueba con un clip programado a 2 minutos.
- Los clips que ya existen no tienen paquete ni miniatura (solo los nuevos y los que rehagas); siguen usando la descripción y hashtags de antes.
- **Estadísticas por clip (vistas, alcance) NO están incluidas**: necesitan leer los insights de Meta con tu token y no puedo verificar ese formato sin tu cuenta. Queda para una mejora aparte.
- Los clips en vivo (modo En vivo) todavía no generan paquete ni miniatura.
- La web no se compiló aquí (sin node_modules): revisé la sintaxis, no el build completo.
