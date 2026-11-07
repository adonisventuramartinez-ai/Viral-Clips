# ClipForge – lista de 3 pasos

Todo el código ya está listo. Solo faltan estas 3 cosas, que van en tus cuentas:

## 1) Supabase (1 minuto)
Supabase → tu proyecto → **SQL Editor → New query** → pega TODO el contenido de
`supabase/setup_completo.sql` → **Run**.
(Se puede ejecutar varias veces sin problema, aunque ya hayas corrido los otros.)

## 2) Vercel (1 minuto)
Vercel → tu proyecto → **Settings → Environment Variables** → agrega:
- Key: `APP_PASSWORD`  · Value: la contraseña que quieras  · Production marcado
Luego **Deployments → ⋯ → Redeploy**.

## 3) Worker en tu PC (doble clic)
1. Instala **Docker Desktop** y ábrelo (espera a que diga "running").
2. Abre la carpeta `worker` y haz doble clic en **INICIAR-WORKER.bat**.
3. La primera vez te pide 3 datos (URL de Supabase, service role key, llave de Groq) y los guarda en `worker\.env`.
   La llave de Groq es gratis: console.groq.com → API Keys.
4. Deja la ventana abierta. Debe decir `Worker listo, esperando trabajos…`

## Probar
Entra a tu página de Vercel → contraseña → **Crear clips** → pega un link de YouTube con un tramo corto
(Desde 0:00, Hasta 10:00) → **Analizar video** → mira el progreso en **Biblioteca**.

## Problemas típicos
- *"Sign in to confirm you're not a bot"*: YouTube bloqueó la descarga. Ver `worker/README.md` (cookies.txt).
- *Página con error 503*: falta `APP_PASSWORD` en Vercel o el Redeploy.
- *"Falta GROQ_API_KEY"*: borra `worker\.env` y vuelve a ejecutar el .bat para reingresar los datos.
