# Crear con IA (video de 60 s desde un prompt)

Sección en `/crear-ia`. Escribes una escena, eliges estilo y el worker entrega un MP4
vertical 1080×1920 de **60 segundos exactos**, con subtítulos, logo y música opcional.

## 1) Base de datos

Si instalaste con `supabase/setup_completo.sql` después de este cambio: no hay nada que hacer.
Si tu base ya existía, ejecuta una vez en Supabase → SQL Editor:

```sql
supabase/0018_ia.sql
```

Agrega `text_to_video` a `sources.kind` y a `jobs.type`. El prompt, el estilo y la música
viajan en `jobs.payload` / `sources.options` (jsonb): **no hacen falta columnas nuevas**.

## 2) Worker

Agrega a `worker/.env` (se lee al arrancar el contenedor):

```env
HF_TOKEN=hf_tu_token_aqui
```

Créalo en <https://huggingface.co/settings/tokens> (token type *Read* suele bastar).

Opcional, para afinar:

| Variable | Default | Qué hace |
|---|---|---|
| `HF_MODEL` | `damo-vilab/text-to-video-ms-1.7b` | Modelo de texto a video. |
| `IA_CLIPS` | `4` | Cantidad de escenas. |
| `IA_CLIP_SECONDS` | `15` | Duración de cada escena. |
| `IA_TOTAL_SECONDS` | `60` | Duración final exacta. |
| `IA_MAX_RETRIES` | `4` | Reintentos ante cold start / 429. |
| `IA_MAX_WAIT` | `25` | Segundos máximos entre reintentos. |
| `IA_REQUEST_TIMEOUT` | `300` | Timeout de cada llamada. |
| `IA_MUSIC_URL` | — | URL de una pista propia; si no, se sintetiza un pad libre de regalías. |
| `REPLICATE_API_TOKEN` + `REPLICATE_VERSION` | — | Plan B por REST (ej. `owner/model:hash`). |

Reconstruye la imagen (`INICIAR-WORKER.bat` lo hace) y espera el mensaje
`Worker listo (… Crear con IA) …`.

## 3) Suposición importante sobre la duración

El modelo de Hugging Face genera clips de **2–3 segundos**, no de 15. Para cumplir los
60 s en free tier, el worker:

1. llama a la API **4 veces** (una por escena),
2. repite cada clip con `-stream_loop` y lo recorta a **15 s** con ffmpeg,
3. los une con `concat` y fuerza `-t 60`.

Si quieres más variedad, sube `IA_CLIPS` (por ejemplo 8 × 7,5 s = 60 s). Ten en cuenta
que cada llamada consume cuota del free tier.

## 4) Procesamiento

Todo es ffmpeg (no se usa MoviePy):

- `scale=1080:1920:force_original_aspect_ratio=increase` + `crop=1080:1920` → nunca distorsiona.
- `fps=30`, `subtitles=` con el trozo de prompt correspondiente a cada escena.
- Logo superpuesto con el mismo `_logo_graph` que el resto del proyecto.
- Audio garantizado (`anullsrc`) y música opcional con `amix` + fundidos.
- Bitrate calculado con `original.size_cap(60)` para no pasar de `CLIP_MAX_MB` (44 MB por defecto).

## 5) Fallos y reintentos

- **503 “model is loading”**: el worker espera el `estimated_time` que devuelve HF (tope `IA_MAX_WAIT`) y reintenta.
- **Sin cupo / 429**: reintento con espera; si configuraste Replicate, pasa a él automáticamente.
- **Falta `HF_TOKEN`**: el trabajo falla con un mensaje claro en el log; no tumba el worker.
- Si se borra la fuente desde la web mientras se genera, el trabajo se cancela en el próximo control.
