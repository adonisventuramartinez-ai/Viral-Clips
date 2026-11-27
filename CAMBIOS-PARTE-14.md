# Parte 14 (parte 2 de 2): cuentas con usuario, nombre y foto de perfil

Ahora la app tiene cuentas. Al abrirla ves arriba tu **foto y tu nombre**, y la sesión se queda guardada 30 días.

## Qué cambia
- **Entrar / Crear cuenta** en la pantalla de login. Usuario (minúsculas, números, punto o guion bajo), contraseña de 8+ caracteres.
- **Código de acceso:** para crear una cuenta hay que escribir la clave de acceso de la app (la variable `APP_PASSWORD` de Vercel). Así nadie de afuera puede registrarse. Máximo 20 cuentas.
- **Barra de arriba:** tu foto y tu nombre; al tocarlos sale el menú: Mi cuenta y foto, Mis redes, Salir. Sin foto se ven tus iniciales.
- **Página Mi cuenta (`/cuenta`):** subir, cambiar o quitar la foto (se achica sola a 256 px, no necesitas Storage), cambiar el nombre y la contraseña, y Salir.
- **Respaldo:** «Entrar solo con la clave de acceso» sigue existiendo, y las sesiones viejas siguen valiendo. Nadie se queda afuera por esta actualización. Quien entre así ve el botón «Crear mi cuenta».
- Tu nombre de cuenta se copia a las páginas que ya usaban «nombre de clipeador» (Mis redes, Estadísticas, En vivo), solo si ese nombre estaba vacío.

## Cómo ponerlo a funcionar
1. Copia los archivos del zip encima de tu proyecto.
2. Supabase → SQL Editor → ejecuta `0016_cuentas.sql`.
3. Sube la web a Vercel. **El worker y Docker no cambian en esta parte.**
4. Abre la app → pestaña **Crear cuenta** → pon el código de acceso (tu `APP_PASSWORD`). Te lleva a Mi cuenta para poner la foto.

## Seguridad
- Las contraseñas se guardan con scrypt y sal propia, nunca en claro. La web no devuelve el hash ni la lista de cuentas.
- La sesión es una cookie firmada, solo del servidor (httpOnly), que dura 30 días. Si cambias `APP_PASSWORD` en Vercel, todas las sesiones se cierran (las cuentas siguen).
- Límite de intentos: 5 fallos cada 15 min por IP en login y en registro, y en cambiar contraseña. Vive en la memoria del servidor: en Vercel frena lo casual, no es un muro perfecto.
- Contraseña mala y usuario que no existe dan el mismo mensaje.

## Lo que NO hace (a propósito)
- **No hay recuperar contraseña por correo.** Si olvidas la tuya: entra con «solo la clave de acceso», borra tu fila en Supabase (Table Editor → `accounts`) y crea la cuenta otra vez.
- **Es identidad, no permisos.** Todas las cuentas ven y hacen lo mismo que antes; no hay roles ni datos separados por usuario.

## Archivos (19)
Web nuevos: `lib/profile.ts`, `lib/password.ts`, `lib/ratelimit.ts`, `lib/session.ts`, `lib/useMe.ts`, `components/Avatar.tsx`, `app/cuenta/page.tsx`, `app/api/registro/route.ts`, `app/api/cuenta/route.ts`, `app/api/logout/route.ts`.
Web cambiados: `lib/auth.ts`, `middleware.ts`, `components/Topbar.tsx`, `app/login/page.tsx`, `app/api/login/route.ts`.
Base de datos: `supabase/migrations/0016_cuentas.sql`, `supabase/setup_completo.sql` (trae también 0015). Pruebas: `test_parte14.mjs`.

## Pruebas
`node --experimental-strip-types test_parte14.mjs` (Node 22.6 o más nuevo): 76 comprobaciones que corren las rutas y el middleware reales contra una base simulada. Cubren registro, login, foto, contraseñas, sesiones falsificadas, vencidas o firmadas con otra clave, y los límites de intentos.
Revisé los tipos con módulos simulados. No pude correr `next build` ni probar contra Supabase real: si algo marca error, pásamelo.
