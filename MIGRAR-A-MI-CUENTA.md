# Pasar ClipForge a TU propia cuenta (Supabase + Vercel + repo nuevo)

Ya tienes Supabase y Vercel creados y quieres **BD limpia** y **repo separado**. Esto es lo que hay que hacer, en orden.

> No pegues llaves en el chat. Yo puedo verificar sin verlas con `/api/health` y con los logs del worker.

---

## 0) Repo nuevo en GitHub

Crea un repositorio **vacío** en GitHub (por ejemplo `Viral-Clips-Mio`) y pégame la URL.
Desde ahí hago el push del código actual para que tengas tu copia independiente.

Mientras tanto, el código ya quedó listo en este repo con el fix del SQL (ver paso 1).

---

## 1) Supabase nuevo — crear tablas

En el proyecto nuevo de Supabase:

1. **SQL Editor → New query**.
2. Pega todo `supabase/setup_completo.sql` y dale **Run**.
   - *(Corregí este archivo: le faltaban `priority`, `run_after`, `max_attempts` y `last_error` de la cola; sin eso el worker no puede tomar trabajos.)*
3. Nueva query con `supabase/0017_transform.sql` → **Run**.
4. Nueva query con `supabase/0018_ia.sql` → **Run**.
5. En **Storage** deben aparecer tres buckets privados: `uploads`, `recordings`, `clips`. Los crea el SQL; si no están, créalos a mano con esos nombres y `public = false`.

No necesitas configurar Supabase Auth: la app usa su propia tabla `accounts` y la clave `APP_PASSWORD`. El primer usuario se crea en `/registro`.

---

## 2) Sacar los datos del Supabase nuevo

En **Project Settings → API** copia (sin mostrarlos en el chat):

| Dato | Dónde va |
|---|---|
| Project URL | `NEXT_PUBLIC_SUPABASE_URL` y `SUPABASE_URL` |
| anon / publishable key | `NEXT_PUBLIC_SUPABASE_ANON_KEY` (y `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` si aparece) |
| service_role / secret key | `SUPABASE_SERVICE_ROLE_KEY` (y `SUPABASE_SECRET_KEY` si el panel la llama así) |

---

## 3) Vercel nuevo

1. **Add New → Project** y selecciona el repo nuevo de GitHub.
2. **Directorio raíz: `./`**. Framework: **Next.js** (deja los valores por defecto).
   - Si Vercel dice “se detectaron varias aplicaciones” y te ofrece **Importar proyecto multiservicio**, **ignóralo**: es un falso positivo. El worker es Python/Docker y no se despliega en Vercel. No hace falta `vercel.json` con `services`, ni `rewrites`, ni `bindings`: la web y el worker se comunican por las tablas de Supabase, no por HTTP.
   - Tampoco agregues la **integración de Supabase** de Vercel si ya creaste el proyecto fuera: puede sobrescribir las variables. Solo pega las variables manualmente.
3. En **Environment Variables** pega las de `vercel-env.example.txt` con tus valores reales.
   - Las cuatro de SUPABASE son las del paso 2.
   - `NEXT_PUBLIC_APP_URL` = la URL que te dé Vercel (termina en `.vercel.app`), sin barra final.
   - `APP_PASSWORD`, `ENCRYPTION_KEY`, `SESSION_SECRET`, `CRON_SECRET` pueden ser los mismos de siempre o nuevos; si cambias `APP_PASSWORD`, las sesiones se cierran y hay que crear el usuario otra vez en `/registro`.
4. **Deploy**.
5. Verifica con `https://TU-PROYECTO.vercel.app/api/health`: debe marcar `ok: true` y los env vars en `true`.

---

## 4) Worker apuntando al Supabase nuevo

En la PC donde vaya a correr el worker (la tuya o la de tu hermano):

1. En el repo nuevo, copia `worker/.env.example` a `worker/.env`.
2. Rellena `SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` con los del paso 2.
3. Pon al menos una llave `GROQ_API_KEY` válida (o las que uses). Las de 401 se descartan solas, pero conviene quitarlas.
4. Arranca:
   - PC con Docker Desktop: doble clic en `INICIAR-SIEMPRE.bat`.
   - Esta PC (sin WSL): doble clic en `INICIAR-DOCKER-LOCAL.bat`.
5. Confirma en los logs: `Worker listo (...), esperando trabajos…`.

**Importante:** solo un worker activo apuntando al Supabase nuevo. Si el worker viejo sigue apuntando al proyecto anterior, no estorba, pero tampoco procesa lo nuevo.

---

## 5) Prueba rápida

1. Abre la web nueva → `/registro` → crea tu usuario (te pedirá el `APP_PASSWORD`).
2. `/crear` → sube un video corto o pega un link → genera clips.
3. `/en-vivo` → graba un directo corto → espera 2 min o dale **Clip ahora**.
4. `/biblioteca` → reproduce y revisa que voz + subtítulos coincidan.

Si el texto sigue desfasado, mueve `SUB_SYNC_OFFSET` en `worker/.env` (`-0.5` o `-0.2`) y recrea el contenedor.

---

## Resumen de lo que NO se migra (porque pediste empezar limpio)

- Usuarios viejos.
- Clips viejos y sus archivos en Storage.
- Historial de publicaciones.

Si luego quieres traer los clips antiguos, se puede con un script que baje del bucket viejo y suba al nuevo; dime y lo preparamos.
