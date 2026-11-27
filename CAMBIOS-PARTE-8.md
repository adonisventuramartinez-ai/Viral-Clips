# Parte 8: cola de publicación automática (Parte 2 del plan)

Copia encima de tu proyecto. Requiere la Parte 7. Pruebas: `python test_parte8.py` (37) + las anteriores; la web compila.

## Antes de usarla
1. Supabase → SQL Editor: `supabase/migrations/0010_cola_publicacion.sql`.
2. Reconstruye el Docker. 3. Sube la web a Vercel (nueva página **Cola** en el menú).
4. En `worker/.env` agrega las credenciales de las redes que quieras y `AUTO_QUEUE=1` (viene APAGADA).

## Qué hace
- **Cola automática** (`autoqueue.py`): toma clips con veredicto "listo" o aprobados por ti (nunca los de revisión/flojos), los mejores primero, y les pone hora en cada red con las horas de la Parte 7. No programa a más de 3 días ni más de 12 en espera por red.
- **Publicador** (`poster.py`): corre en un hilo propio, así publica a su hora aunque el worker esté grabando un directo (antes la programación esperaba a que estuviera libre).
- **Redes**: Facebook Reels (el que ya tenías), **Instagram Reels** (`publisher_ig.py`) y **YouTube Shorts** (`publisher_yt.py`). Cada una se activa sola si tiene credenciales.
- **Página Cola**: ver próximas y historial, mover la hora, cancelar y reintentar. Muestra si la cola está encendida y qué redes están conectadas.
- **Contra doble publicación**: se reserva el post antes de subir; si el worker se cae a mitad queda en error y NO se repite solo. Los errores tampoco se reintentan solos: tú decides con ↻ (revisa antes tu página).
- La programación manual de Facebook en la tarjeta del clip sigue funcionando y cuenta como hora ocupada.

## Lo que necesitas conseguir (yo no puedo)
- **Instagram**: cuenta Business/Creator enlazada a tu página, `IG_USER_ID` y un token con permiso `instagram_content_publish`.
- **YouTube**: proyecto en Google Cloud con YouTube Data API v3, client id/secret y un refresh token de tu canal.
  Ojo: los proyectos sin auditar suben los videos como PRIVADOS; hay que pasar la auditoría de Google. Cuota: ~6 subidas al día.
- **TikTok no está**: su API de publicación exige aprobación de la app; por ahora sigue el botón 📋 copiar.

## Límites (honestos)
- **No pude probar contra Facebook, Instagram ni YouTube reales** (no tengo tus cuentas). Probé la lógica y los pasos de cada API con respuestas simuladas. Haz la primera prueba con UN clip y `AUTO_NETWORKS=facebook`.
- Facebook: el Reel sale con el texto de la Parte 7; la miniatura personalizada no se sube.
- Si pones `AUTO_QUEUE=1`, el worker publica sin preguntarte. Para revisar antes, déjalo en 0 y usa "🕐 Programar a la mejor hora" clip por clip.
