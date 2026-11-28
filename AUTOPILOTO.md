# 🤖 Piloto automático (Alofoke en vivo → clips → páginas)

## Cómo funciona

1. El worker graba el directo y saca clips (máx. **3** por revisión, sin cambios). Los de La Casa salen en formato **🏠 Cara grande arriba + fondo difuminado abajo** (ver `FORMATO-CASA.md`).
2. `Hacerlo viral` los puntúa. Con el piloto encendido, los `ready` pasan a `approved` solos.
3. Cada clip entra en la cola del worker (**cada 2 min**) y se programa en **todas las páginas marcadas** (`facebook:<id>`), con 45 s de separación entre páginas y anti-duplicado por clip+página.
4. A la hora, el worker llama a la web con una firma HMAC hecha con **la misma llave R2/Tigris**; la web busca el token fresco de la página, firma el clip y publica el Reel.
5. Todo se hace sin llaves nuevas y sin pedir contraseñas.

## Importante: hay DOS Supabase

| Proyecto | Qué guarda | Dónde se configura |
|---|---|---|
| Supabase de la **web** | `cuentas_fb`, `posts_programados`, la config del piloto | Vercel |
| Supabase del **worker** | `clips`, `posts`, `connections`, directos | `worker/.env` |

No son el mismo proyecto. Por eso el puente va firmado con `R2_SECRET_ACCESS_KEY` (idéntico en ambos lados) y no con la llave de servicio.

## Pasos (una vez)

1. **SQL**: pega `supabase/PEGAR-AHORA.sql` en **las dos Supabase** (la de la web y la del worker) y dale Run. Empieza con SQL válido (sin encabezados que rompan el editor) y arregla el buscador + el piloto de una vez. Se puede correr varias veces.
2. **Vercel**: confirma las 6 variables R2/Tigris en **Production** (`STORAGE_DRIVER`, `R2_ENDPOINT`, `R2_REGION`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_CLIPS_BUCKET`) y redeploy **sin caché**. Abre `/almacenamiento`: debe decir **Conexión OK**.
3. **Worker**: `worker/.env` ya tiene `STORAGE_DRIVER=r2`, `WEB_URL` y la misma llave R2. Reconstruido con `docker compose -f worker/docker-compose.yml build worker && docker compose -f worker/docker-compose.yml up -d --force-recreate worker`.
4. **Cuenta**: en el menú **Facebook**, conecta tu cuenta (si ya está, no la toques). La página **🤖 Piloto automático** lee ahí los proyectos y páginas.
5. **Encender**: entra a `/autopiloto`, marca las páginas y dale **🚀 Encender piloto**. El worker lee el cambio en ≤15 s.

## Verificación en vivo

- En los logs del worker debe aparecer: `Piloto: N publicación(es) en X página(s)`.
- Si sale `No autorizado (falta la llave R2/Tigris en Vercel)`, falta el paso 2.
- Si sale `Falta correr 0020_autopiloto.sql`, falta el paso 1 en la Supabase indicada.
- Si `/autopiloto` no muestra páginas, la cuenta no está conectada en el menú **Facebook**.
