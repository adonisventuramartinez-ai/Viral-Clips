# Mejora 2: retención (ritmo, zooms de corte y apertura directa)

Aplícala **después** de la Mejora 1 (copia las carpetas encima del proyecto). Sin SQL nuevo.

## Qué hace
- **Quitar silencios y muletillas** (`worker/tighten.py`, nuevo). Pausas de más de 0.65 s se acortan a 0.3 s, se recorta el silencio del inicio y del final, y se quitan "eh", "mmm", "em", "hmm" (no toca "este", "o sea" ni "ah", porque cambiarían lo que dice la persona). Nunca quita más del 30 % del clip, y si ahorra menos de 0.6 s no lo recodifica. Los subtítulos se mueven con los cortes. Cada corte lleva un fundido de 20 ms para que no suene el "clic".
- **Zoom suave en los cortes**: un acercamiento del 6 % en un tramo sí y otro no, para que el salto no se note. Nada en los primeros 2 s y máximo 8 por clip.
- **Cuándo se aplica**: en modo Automático solo en Podcast, Entrevista, Reality, Directo y General. En juegos y GTA no (ahí el silencio es parte de la jugada). Se puede forzar en Crear > Audio y efectos > *Quitar silencios y muletillas* (Automático / Siempre / Nunca), o con `CLIP_TIGHTEN=1` o `0` en el `.env` del worker.
- **Apertura directa (opcional)**: `INTRO_MODE=cold` en el `.env`. El clip arranca de inmediato y el texto de contexto sale encima de los primeros 3 s, en vez de la tarjeta antes del clip. Mejora la retención, pero **se pierde la voz narradora de la intro**, y esa voz es parte del "aporte propio" que premia Facebook. Por eso por defecto sigue `INTRO_MODE=card`.

## Pruebas
`python test_mejora2.py` (lógica de cortes, muletillas, límite del 30 %, zooms, opciones y un render real con ffmpeg). Todas las pruebas anteriores siguen pasando.

## Límites
- Probé con tiempos de palabras escritos a mano y con video de prueba, **no con una transcripción larga de Whisper**. Los tiempos de Whisper pueden ser imprecisos al cortar; si notas palabras mochas, sube `GAP_MIN` o `PAUSE_KEEP` en `tighten.py`.
- La web no se compiló aquí: corre `npm run build` antes de subir.
- Se codifica una copia intermedia del tramo (calidad casi sin pérdida), así que cada clip con recorte tarda unos segundos más.
