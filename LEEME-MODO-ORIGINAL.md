# Modo Original (sin cara ni voz tuya)

1. Copia tu `.env` en `worker/` (esta versión no lo trae). Agrega si quieres:
   - `SHOW_NAME`, `PAGE_NAME`, `CREDIT_LINE`, `NARRATOR_VOICE` (es-DO-EmilioNeural o es-DO-RamonaNeural)
   - `FB_AUTOPUBLISH=1`, `FB_PAGE_ID`, `FB_PAGE_TOKEN`, `FB_MIN_SCORE=75`, `FB_MAX_PER_JOB=3` (publicar Reels solo; apagado por defecto)
2. Reconstruye el worker (Docker) para que instale `fonts-montserrat`, `opencv-python-headless` y `edge-tts`.
3. En la web: Ajustes de IA → Modo Original. Ahí eliges voz, dramómetro, encuesta A/B, TOP y crédito.
4. La voz usa internet (edge-tts). Si no hay internet el clip sale igual, sin voz.
5. Modo Original aplica a videos nuevos (Crear clips). Los re-renders y el modo En vivo salen sin tarjetas.
