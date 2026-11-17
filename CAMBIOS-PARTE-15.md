# Parte 15: gancho del inicio y Modo Original «brutal»

Copia encima de tu proyecto. **No hay migración nueva.** Reconstruye el Docker del worker (`INICIAR-SIEMPRE.bat`) y sube la web a Vercel.

## El problema del gancho
1. Con Modo Original, cada clip empezaba con una **tarjeta narrada de 2+ segundos** antes del video. La gente decide en 2 s si se queda: se iban ahí.
2. La IA a veces cortaba el clip en «bueno, eh…», en un saludo o en una frase que depende de la anterior («pero eso no es lo peor»).
3. El texto de arriba podía ser vacío («MIRA ESTO») y el gancho se pisaba con el dramómetro.

## Qué cambia
- **Apertura directa (nuevo por defecto):** el primer cuadro YA es el video. El gancho aparece arriba desde el cuadro 0 con un golpe de escala; ~1 s después sale el contexto debajo («Antes de esto…»). Nada antes del clip. La tarjeta de antes sigue existiendo (Ajustes → «Cómo empieza el clip»).
- **Empezar en lo mejor (`hook.py`):** mueve el inicio hasta 6 s a la primera frase fuerte (pregunta, algo que sorprende) y, si no hay una mejor, quita muletillas sueltas del arranque. Solo mueve si la frase nueva puntúa 10+ puntos más, el clip sigue durando 12 s o más y entra en un límite de frase. No cambia lo que se dice.
- **Gancho concreto:** si la IA da uno vacío o repetido («MIRA ESTO», «INCREÍBLE»), se saca uno de la frase más fuerte del propio clip (sin insultos). Máx. 7 palabras / 44 caracteres.
- **Prompt de la IA** más exigente con el inicio y con el gancho (promesa o duda abierta, sin frases vacías).
- **Dramómetro animado:** la barra se llena en ~1 s y dice el nivel (CALENTITO / TENSO / EXPLOSIVO).
- **Encuesta final con paneles de color:** pregunta grande, A azul y B rojo entrando deslizando, «COMENTA A O B» y el nombre de tu página. Los bandos ahora se piden claros y opuestos.
- **TOP** con un cuadro real de cada clip de fondo (antes, pantalla lisa).
- **Tamaño garantizado:** el archivo final nunca pasa de `CLIP_MAX_MB` (44 por defecto; Supabase rechaza 50 MB). Antes, al envolver el clip con tarjetas, el re-encode a CRF 18 no tenía tope y un clip de ~60 s podía pasarse. `render._bitrate` usa el mismo presupuesto (tope de calidad 10 Mbps).

## Interruptores
Web → Ajustes → Modo Original: «Cómo empieza el clip» y «Empezar en lo mejor». En `worker/.env`: `INTRO_MODE=cold|card`, `SMART_START=1|0`, `CLIP_MAX_MB=44`. La web manda sobre el `.env` para lo que guarda.

## Pruebas
`test_gancho.py` (29) y `test_original2.py` (38, con ffmpeg real: comprueba que en modo directo el primer cuadro es el video y que la duración es clip + cierre, sin tarjeta antes). `test_framing.py` se alineó al nuevo tope de tamaño. Corren las 23 suites del worker: todas pasan.

## Límites (honestos)
- **No puedo medir retención.** Esto quita las causas conocidas de abandono, pero no garantiza que un clip retenga: lo decide el contenido. Mira «retención» en las estadísticas de Facebook de los primeros clips y compara.
- La voz (edge-tts) y Facebook real no se probaron aquí (sin internet). Las pruebas visuales se hicieron con una fuente de reemplazo; en tu Docker sale Montserrat (queda un poco más ancho: revisa un clip con gancho de 7 palabras).
- Mover el inicio quita hasta 6 s del arranque: puede quitar contexto. Si un clip pierde sentido, apaga «Empezar en lo mejor».
- En modo directo el contexto se lee, pero ya no se narra (la voz taparía a quien habla). La encuesta del final sí se narra.
- No corrí `next build`: revisé los tipos de la ruta y la sección editada con módulos simulados.

## Archivos
Nuevos: `worker/hook.py`, `worker/test_gancho.py`, `worker/test_original2.py`.
Cambiados: `worker/original.py`, `worker/analyze.py`, `worker/render.py`, `worker/main.py`, `worker/config.py`, `worker/test_framing.py`, `worker/.env.example`, `app/api/original/route.ts`, `app/ajustes/page.tsx`, `LEEME-MODO-ORIGINAL.md`.
