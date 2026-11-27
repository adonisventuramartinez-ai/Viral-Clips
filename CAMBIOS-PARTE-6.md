# Parte 6: GTA 6, voces en vivo y opciones en la web

Incluye las Partes 1 a 5. Sin SQL nuevo. Pruebas: `test_parte6.py` (53) y todas las anteriores pasan.

## GTA 6 (sale el 19 de noviembre de 2026, solo PS5 y Xbox Series X|S; PC no anunciado)
- **Nuevo tipo "GTA 6 acción"** en Crear, En vivo y Canales vigilados. La IA sabe que es Vice City y Leonida y premia la **primera reacción**, los descubrimientos, los bugs graciosos, tiroteos, persecuciones y explosiones. Zoom + cámara lenta + disparos/explosiones por audio, como GTA 5.
- **Se activa solo**: si eliges Juegos, GTA o General y el nombre del juego dice "GTA 6", "GTA VI", "Grand Theft Auto VI" o "Leonida", usa este perfil.
- **Lo que NO está listo**: las pantallas WASTED/BUSTED se reconocen por el color y la posición de GTA 5, y yo no he visto la de GTA 6, así que **en este perfil están apagadas**. Mientras tanto la verificación con imágenes (👁) hace de segunda opinión. Cuando salga, mándame 2 o 3 clips (con una muerte y una captura de policía) y la calibro.
- Los umbrales de disparos y explosiones siguen sin calibrar con tu gameplay (igual que antes).

## Voces en vivo
El modo En vivo ahora recuerda las voces entre trozos: la misma persona conserva su P1/P2 durante todo el directo (probado con dos trozos con distinto volumen). Funciona en GTA RP, Reality, Podcast, Entrevista, Directo y General.

## Web: audio y efectos
En **Crear**, debajo de "Barra de progreso": desplegable **Audio y efectos** con pitido, volumen parejo, zoom y cámara lenta. Cada uno: Automático / Siempre / Nunca. Se guarda también en tus configuraciones guardadas. La ruta `/api/jobs` ya lo acepta.
- **No pude compilar la web aquí** (no hay node_modules): revisé la sintaxis con el compilador de TypeScript y no dio errores de sintaxis ni de mis cambios, pero **corre `npm run build` antes de subir**. Si sale algún error, pásamelo.
- En la página de En vivo y en Canales vigilados todavía no hay ese desplegable (usa el `.env` del worker).

## La Casa de Alofoke 3 (lo que encontré en la prensa, sin confirmar por mí)
- Según los artículos, estrena en diciembre de 2026 y llega hasta principios de enero de 2027. Monchy Cadena fue anunciado como primer participante; el elenco completo no estaba confirmado.
- Alofoke dijo que permitirá monetizar el contenido del reality en redes. **Lee las condiciones oficiales** antes de publicar, porque no sé qué exigen.
- Cuando se sepan los participantes, ponlos en `CAST_NAMES` en el `.env` para que los subtítulos y la IA escriban bien los nombres.
