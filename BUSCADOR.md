# Buscador de clips virales (TikTok / Instagram Reels)

El buscador entra por **Buscador viral** en el menú. Busca videos que están subiendo, descarta los que tienen
marca ajena y encola los mejores para que sigan por el pipeline normal de ClipForge:

```
búsqueda → perfiles/links públicos → ranking → filtro de marca → job 'download'
        → transcripción + IA → clip 1080×1920 ≤44 MB → Storage 'clips' + tabla 'clips' (web)
        → cola automática → Facebook
```

## Instalación (una vez)

1. En Supabase > SQL Editor, ejecuta `supabase/migrations/0019_buscador.sql`.
   Si tu base es nueva, también está al final de `supabase/EJECUTAR-TODO.sql`.
   Esto crea `clip_searches`, `clip_search_results` y permite el tipo de trabajo `search`.
2. Redeploy de Vercel y reconstrucción del worker:

   ```powershell
   cd C:\DockerVM\vagrant
   vagrant ssh -c "cd /vagrant && docker-compose up -d --build --force-recreate"
   ```

3. Para que los clips lleguen **también a Facebook**, deja `AUTO_QUEUE=1` en `worker/.env` (o el botón
   «Cola automática» de la web en `/cola`) y configura `FB_PAGE_ID` + `FB_PAGE_TOKEN` en «Conectar cuentas».
   La web ya recibe todos los clips automáticamente.

## Cómo buscar

- **Perfiles**: escribe `@usuario` o pega `https://www.tiktok.com/@usuario`. Se leen sus videos con yt-dlp.
- **Links directos**: pega URLs concretas de TikTok o Reels; se consulta cada video por separado.
- **Tema**: el campo «Tema» solo nombra la búsqueda. TikTok bloquea la búsqueda web (devuelve captcha) y no
  ofrece extractor de búsqueda, así que el rastreo se hace sobre los perfiles/links que indiques.
- Puedes poner cuántas vistas mínimas, antigüedad, resultados y cuántos se encolan solos (`0` = solo mirar).
- Si un resultado no se encoló solo, dale a **📥 Encolar** o a **⚡ Encolar todos**.

## Filtros

- Descarta videos muy cortos/largos, viejos, con pocas vistas o con poca interacción (likes/vistas).
- Puntaje = vistas + velocidad (vistas por hora) + interacción + frescura + comentarios.
- **Sin marca**: títulos publicitarios se descartan de entrada; a los mejores se les mira la miniatura con
  un modelo de visión y se rechazan si tienen logo o marca de otro creador (`SEARCH_BRAND_FILTER=1`).
  Si no hay proveedor de visión configurado, el filtro de imagen se omite y se avisa en el log; el de texto sigue.
- Evita volver a encolar un video que ya existe como fuente en la web.

## Ajustes en `worker/.env`

| Variable | Valor | Para qué |
|---|---|---|
| `SEARCH_ACCOUNTS` | `12` | Máximo de perfiles por búsqueda |
| `SEARCH_INSPECT` | `8` | Máximo de videos a los que se revisa la marca con visión |
| `SEARCH_MIN_VIEWS` | `10000` | Vistas mínimas |
| `SEARCH_MAX_AGE_HOURS` | `72` | Antigüedad máxima |
| `SEARCH_MIN_ENGAGEMENT` | `1.5` | Likes / vistas mínimo en % |
| `SEARCH_BRAND_FILTER` | `1` | Rechazar marcas ajenas |
| `SEARCH_SEEDS` | vacío | Perfiles por defecto si no envías ninguno |
| `COOKIES_FILE` | — | Necesario para hashtags de Instagram; TikTok no lo necesita para perfiles |

## Notas

- Instagram `instagram:user` está marcado como roto en yt-dlp; con `COOKIES_FILE` se pueden usar
  `https://www.instagram.com/explore/tags/<tag>/` y links directos de reels.
- Un perfil privado o una red que bloquea la IP se omite sin detener la búsqueda; el resto de resultados sigue.
- Reseta los derechos de cada video: usa perfiles propios o contento con permiso; el crédito se añade con el Modo Original.
