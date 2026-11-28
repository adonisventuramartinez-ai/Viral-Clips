# 🏠 Formato "La Casa" — investigación y decisión

## Lo que hace la competencia (buscado y verificado)

| Herramienta / fuente | Cómo reencuadra | Qué dice para momentos con varias personas |
|---|---|---|
| **OpusClip** (docs oficiales) | `Fill` = recorta al que habla y llena 9:16 (es el **default**). También `Fit`, `Split`, `Three`, `Four`, `Screenshare` y `Gameplay` (30% cara / 70% juego). La IA elige el layout que conviene a cada clip y se puede corregir por segmento. | `Split` solo sirve si los dos salen juntos en el cuadro original. Si hay desacuerdo o reacción, un solo crop se queda corto. |
| **CapCut** | Auto Reframe + relleno de fondo (difuminado, color o imagen). Es la técnica más copiada para pasar 16:9 a 9:16 sin barras negras. | No elige por persona: el editor decide. |
| **Cut.Pro** (guía 2026) | Cuatro layouts: **primer plano del que habla**, **split**, **cuadro completo con fondo difuminado** y **corte a la reacción**. Frase clave: *“el error más común no es elegir el layout equivocado, es elegir uno y usarlo para todo el clip”*. | Full screen para monólogo; split para ida y vuelta; difuminado **solo 2-3 s** para el grupo; corte al que escucha cuando la reacción es el gancho. |
| **Vyroclips** (guía de multi-speaker, con sesgo de competidor) | Si el clip depende de **discusión, risa, sorpresa o timing**, usa split/multi-cara; si es una respuesta limpia, funciona el crop al hablante. | Advertencia real: el crop que sigue solo la voz se come la reacción que vende el clip. |
| **AspectShift** (pruebas propias, también vendor) | 1080x1920 manda; el **relleno difuminado** se vio más intencional/profesional que el center crop o las barras negras, y conserva más cuadro. | Pero no es para todo el clip: caras pequeñas = la gente no se detiene. |

Fuentes: [Opus Clip layout docs](https://help.opus.pro/docs/article/layout-and-reframing), [Cut.Pro vertical framing 2026](https://cut.pro/en/blog/vertical-framing-multi-person-podcast-2026), [Vyroclips multi-speaker guide](https://vyroclips.com/opus-clip-face-tracking-glitch-multi-speaker-interviews), [AspectShift tested aspect ratios](https://aspectshift-htov.com/blog/best-aspect-ratio-for-youtube-shorts-tiktok-and-instagram-reels-tested-and-explained).

## Veredicto

**No gana un formato fijo. Gana el cambio por momento.** El default más usado es `Fill` (cara llena), pero en un reality el drama está en el cruce de miradas: ahí los profesionales pasan a `split`. El fondo difuminado es contexto, no protagonista.

Por eso el formato de ClipForge quedó así:

1. **Una persona habla / confiesa** → `casa`: cara grande arriba (1500 de 1920 px, ojos en el tercio superior) + franja de 420 px abajo con el mismo momento difuminado y oscurecido. Es `Fill` con contexto, sin caer en "video reciclado de horizontal".
2. **Dos personas claras en el tramo** → el worker detecta las dos caras y cambia solo a `duo` (una arriba, otra abajo). Es el `Split` que recomiendan Opus y Cut.Pro para peleas y remates.
3. **Recuadro manual** → manda el usuario, el piloto no lo pisa.
4. **Juegos, GTA, podcast, entrevistas** → conservan su layout; esto solo aplica al perfil `reality`.

`CLIP_REALITY_LAYOUT` en `worker/.env`:

- `auto` (default): cara grande + dúo automático.
- `casa`: siempre cara grande con contexto.
- `crop`: vuelve al vertical puro.

## Ajustes respecto a la versión anterior

- Panel de cara: **1250 → 1500 px** (más cerca de lo que recomiendan para mobile).
- Franja difuminada: **670 → 420 px** (contexto, no media pantalla).
- Subtítulos: `MarginV` **700 → 450** para que caigan en la costura entre la cara y el contexto, lejos de la UI de Reels (Meta pide 14% arriba, 35% abajo, 6% lados).

## Pruebas

- `test_formato_casa.py`: **11/11** (default, respeto del recuadro manual, apagado por variable, grafo ffmpeg, dos caras → dúo, podcast → casa).
- `test_autopiloto.py`: **14/14**.
- `test_parte13.py`: **14/14**.

**Honestidad:** esto es investigación + lógica probada en código, no un test A/B con tus métricas reales de Facebook/Reels. Cuando prendas el vivo, comparamos el primer clip de confesión (debe salir cara grande) contra el primero de pelea (debe salir dúo). Si el dúo se ve muy pequeño, subimos `DUO_H` y listo.
