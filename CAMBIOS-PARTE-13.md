# Parte 13 (parte 1 de 2): botones de Clips automáticos y Cola automática

Ya no hay que tocar `worker/.env` ni reiniciar nada para encender lo automático: se hace con un botón en la web.

## Dónde están
- **Clips automáticos** → botón arriba de la página (antes era el aviso «pon DISCOVER=1»).
- **Cola** → botón arriba de la página (antes era el aviso «pon AUTO_QUEUE=1»). Al encenderlo pide confirmación, porque a partir de ahí se publica solo.

Cada botón dice si el worker ya lo aplicó («El worker confirma: encendido»), si está aplicando, si el worker está apagado, o si tu worker es de una versión anterior.

## Cómo manda cada cosa
- Si **nunca tocas** el botón, sigue mandando lo que diga `worker/.env` (DISCOVER / AUTO_QUEUE). Tu flujo actual no cambia.
- Si lo **tocas**, el botón gana sobre el `.env`, encendido o apagado.
- «Usar lo del .env» (aparece solo si ya lo tocaste) devuelve el control al `.env`.
- El worker lee el botón cada ~15 s: no hay que reiniciarlo.
- Sin la migración, todo sigue como antes (manda el `.env`).

## Cómo ponerlo a funcionar
1. Copia los archivos del zip encima de tu proyecto.
2. Supabase → SQL Editor → ejecuta `0015_interruptores.sql`.
3. Reconstruye el Docker con `INICIAR-SIEMPRE.bat` (el worker necesita el código nuevo **una vez**) y sube la web a Vercel.
4. Entra a **Clips automáticos** y enciende el botón. Agrega UNA fuente y mira «Lo que encontró» antes de poner más.

## Archivos (14)
Web: `app/api/interruptores/route.ts` (nuevo), `lib/useSwitches.ts` (nuevo), `components/SwitchCard.tsx` (nuevo), `app/auto/page.tsx`, `app/cola/page.tsx`.
Worker: `db.py`, `autoqueue.py`, `discover.py`, `main.py`, `test_parte13.py` (nuevo), `.env.example`.
Base de datos: `supabase/migrations/0015_interruptores.sql` (nueva), `supabase/setup_completo.sql`.

## Pruebas
- `test_parte13.py`: 14 comprobaciones (el botón gana al .env en los dos sentidos, sin migración manda el .env, no golpea Supabase en cada vuelta, Clips automáticos y Cola obedecen el botón).
- Siguen pasando las Partes 8, 9, 11 y 12.
- Revisé los tipos de los archivos nuevos con módulos simulados (sin errores en el código nuevo). No pude correr `next build` aquí: si marca algo, pásame el error.
- No probé contra Supabase ni Facebook reales.

## Seguridad
Tu zip trae `worker/.env` y las cookies de YouTube. No van en este zip. Y como pegaste el `.env` completo en el chat, regenera las llaves de Supabase (service role), Groq y Gemini.

## Sigue: Parte 14
Cuentas con usuario y contraseña, nombre y foto de perfil que se vea al abrir la app, y que la sesión se quede guardada.
