# Parte 11: worker siempre activo en Docker (Parte 5 del plan)

Copia encima de tu proyecto (después de la Parte 10). Sin SQL nuevo. Pruebas: `python test_parte11.py` (37).

## Cómo dejarlo siempre activo
1. Abre Docker Desktop → Settings → General → marca **Start Docker Desktop when you sign in**. (Sin esto, al reiniciar la PC Docker no abre y el worker tampoco.)
2. Cierra el worker viejo si lo tenías abierto con `INICIAR-WORKER.bat` (dos workers a la vez se pisan los trabajos; el nuevo script lo detecta y avisa).
3. En la carpeta `worker`, doble clic en **INICIAR-SIEMPRE.bat**. Construye, enciende en segundo plano y puedes cerrar la ventana.
4. Otros botones: **VER-LOGS.bat** (qué está haciendo) y **DETENER-WORKER.bat** (apagarlo).

`INICIAR-WORKER.bat` sigue existiendo para la primera vez (te pide los 3 datos y crea `.env`) o para probar con la ventana abierta.

## Qué hace para no caerse
- `restart: unless-stopped`: si el worker falla, si reinicias la PC o si Docker arranca, se levanta solo. Solo se queda apagado si TÚ lo detienes.
- **Salud**: un hilo marca "sigo vivo" cada 30 s (aunque haya un render o un directo de horas) y Docker lo revisa; si deja de marcar, aparece `unhealthy` en `docker compose ps`.
- **Reinicio diario** a las 4 a. m. (`RESTART_HOUR`, -1 = nunca): al volver baja el yt-dlp más nuevo (YouTube cambia casi cada semana). Solo reinicia si no hay trabajos, ni directo grabando, ni nada publicándose o programado en los próximos 10 min.
- **Recuperación al arrancar**: los videos/clips que quedaron a medias por un reinicio vuelven a la cola de inmediato (antes esperaban 3 h). Un directo cortado no se retoma. Si un trabajo ya falló varias veces va a error en vez de repetirse para siempre. Se apaga con `RECOVER_ON_START=0`.
- **Apagado ordenado**: `docker stop` y el apagado de Windows ya no esperan 10 s para cortar a la fuerza.
- Los videos en proceso (`work/`), los logs (`logs/worker.log`) y el modelo de Whisper se guardan fuera del contenedor, así que un reinicio no los pierde ni vuelve a bajar el modelo.

## Límites (honestos)
- **No pude construir ni correr el contenedor aquí** (sin red ni motor de Docker). Sí validé el `docker-compose.yml` con `docker compose config` y probé la lógica (37 pruebas: reinicio diario, latido, healthcheck, recuperación, seguridad). La primera vez, mira `VER-LOGS.bat` y `docker compose ps`: debe decir `healthy` en ~3 min.
- **Tu PC tiene que estar encendida.** Siempre activo significa "se levanta solo", no "funciona con la PC apagada o en suspensión". Para 24/7 de verdad hace falta un servidor (VPS) o una PC que no se duerma; el mismo `docker-compose.yml` sirve allí.
- Una publicación a medias cuando se apaga la PC queda marcada como error («revisa tu página antes de reintentar») y no se repite sola, para no publicar doble.
- Las cookies de YouTube y el logo van dentro de la imagen (como antes): si los cambias, vuelve a ejecutar INICIAR-SIEMPRE.bat.
- El reinicio diario usa tu huso `POST_TZ_OFFSET` (-4).

## Archivos
Nuevos: `worker/docker-compose.yml`, `docker-entrypoint.sh`, `healthcheck.py`, `lifecycle.py`, `INICIAR-SIEMPRE.bat`, `iniciar-siempre.ps1`, `DETENER-WORKER.bat`, `VER-LOGS.bat`, `.gitattributes`, `test_parte11.py`.
Cambiados: `worker/Dockerfile`, `.dockerignore`, `config.py`, `db.py`, `main.py`, `.env.example`, `EMPIEZA-AQUI.md`.
