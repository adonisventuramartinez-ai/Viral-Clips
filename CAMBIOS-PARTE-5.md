# Parte 5: quién habla

Incluye las Partes 1 a 4. Sin SQL nuevo. Pruebas: `python test_parte5.py` (17) y todas las anteriores pasan.

## Qué hace
- **Separa voces sin instalar nada** (`voices.py`, numpy + scipy): agrupa las frases por timbre y tono y las etiqueta P1, P2… en orden de aparición.
- **La IA sabe quién dice qué**: la línea sale `[123] P2: texto`, útil para entrevistas, podcast y reality.
- **Discusiones más precisas**: nueva pista en el detector de la Parte 3: ≥ 4 cambios de persona en 8 s. Sigue exigiendo que coincidan 2 pistas, así que habla alternada con volumen normal no marca.
- **Subtítulos por persona sin pyannote**: usan estas etiquetas, y el color de cada persona es el mismo en todos los clips del mismo video.

Se aplica en GTA RP, Reality, Podcast, Entrevista, Directo y Auto. No en GTA acción ni Juegos (ahí casi nadie "conversa"). Se apaga con `VOICES=0`.

## Limitaciones
- **Probado solo con voces sintéticas** (3 voces con tono y timbre distintos: separó las 3 sin errores). Las voces reales con música, eco o gritos son más difíciles; si ves una persona partida en dos, sube `VOICE_THRESHOLD`; si dos personas salen como una, bájalo.
- Voces muy parecidas (dos hombres de tono similar) se pueden mezclar.
- **Una etiqueta por frase**: si dos hablan a la vez, gana la que domina la frase. No cuenta "cuántos hablan a la vez".
- No conoce nombres: dice P1, P2, no "Alofoke". Asignar nombres necesitaría muestras de cada voz.
- **En vivo no está conectado** (las ventanas son cortas y la numeración cambiaría entre revisiones). Sí funciona en videos y al volver a renderizar un clip.
- Tiempo: en mi prueba, cerca de 1 minuto de cálculo por cada hora de video (un VOD de 4 h, unos 3 minutos; tu equipo puede variar). Se lee un máximo de 4 h.
- pyannote (Parte 4) queda como opción si lo instalas, pero solo se usa si las voces no vienen ya etiquetadas.
