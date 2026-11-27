# Modo Transformar (Anti-Penalización)

Toma un video externo (TikTok, Instagram, un MP4 que ya bajaste) y lo convierte en un clip 1080×1920 con **aporte propio**: voz narradora, tarjeta de contexto, dramómetro, encuesta A/B, tu logo y descripción con punto de vista. Ideal para que Facebook no lo trate como contenido reciclado.

## 1) Base de datos

Si instalaste la base con `supabase/setup_completo.sql` **después de este cambio**, no hay nada que hacer.

Si tu base ya existía, ejecuta en Supabase → SQL Editor:

```sql
supabase/0017_transform.sql
```

Agrega `transform` a `sources.kind` y a `jobs.type` (y asegura el bucket privado `uploads`).

## 2) Worker

Actualiza la imagen (`INICIAR-WORKER.bat` reconstruye) y, si quieres ajustar el comportamiento, agrega a `worker/.env`:

| Variable | Default | Qué hace |
|---|---|---|
| `TRANSFORM_MAX_MB` | `45` | Tope del archivo subido. |
| `TRANSFORM_MAX_SECONDS` | `600` | Si el video es más largo, solo se usan los primeros 10 min. |
| `TRANSFORM_DEFAULT_SCORE` | `78` | Puntaje inicial del clip transformado. |
| `TRANSFORM_ALWAYS_ORIGINAL` | `1` | Fuerza el Modo Original aunque la petición diga lo contrario. |
| `TRANSFORM_INTRO` | `card` | Tarjeta narrada antes del video (usa `cold` si prefieres arrancar con el video). |

El worker ya tiene `gTTS` como plan B de voz (después de `edge-tts`, con timeout para no colgarse).

## 3) Uso

1. Entra a **/crear** y elige la pestaña **✨ Transformar**.
2. Sube el archivo (o pega un link directo `.mp4`) y deja activo **Modo Original**.
3. Ajusta tipo de contenido (por defecto *Podcast*), plantilla de marca y encuadre (se fuerza `crop`).
4. Clic en **Transformar y blindar para Facebook**.
5. Mira el progreso en **Biblioteca**. El clip se guarda en el bucket `clips`.

## Límites y decisiones técnicas

- **Vercel** admite ~4.5 MB por request. Los archivos de hasta 4 MB van por `FormData` a `/api/jobs`; los más grandes se suben directo a Supabase Storage con una URL firmada de `/api/uploads/sign` y solo viaja la ruta (`upload_path`).
- El worker baja el archivo desde Storage con la service role (la URL firmada es un respaldo).
- Todo se normaliza con **ffmpeg** a 1080×1920 (`scale` + `crop`, sin distorsión), con audio garantizado (silencio si el original no trae pista de audio).
- El bitrate se calcula con `original.size_cap()` para que el MP4 final **nunca supere 44 MB** (tope de Supabase es 50 MB).
- Los videos de más de 10 minutos se recortan automáticamente para evitar que el worker se caiga por falta de memoria/disco.
- Si falla la voz o la envoltura del Modo Original, se sube igual el video normalizado: el trabajo no se pierde y es reintendentable.
- El archivo subido se conserva en `uploads/incoming/` para permitir reintentos; puedes borrarlo luego desde Supabase Storage.
