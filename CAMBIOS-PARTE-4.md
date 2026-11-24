# Parte 4: video y audio

Incluye todo lo de las Partes 1 a 3. Sin SQL nuevo. Pruebas: `python test_parte4.py` (75 pruebas) y todas las anteriores pasan.

| Función | Qué hace | Se apaga con |
|---|---|---|
| Pitido en groserías | Silencia la palabra y pone un pitido de 1 kHz; el subtítulo sale `p***`. Compara palabras enteras, así "Singapur" o "vergüenza" no se tocan. | `CLIP_BLEEP=0` |
| Volumen a -14 LUFS | Mide el clip y lo ajusta en dos pasadas (exacto). | `CLIP_LOUDNORM=0` |
| Zoom | Acercamiento de ~10 % en una explosión, ráfaga de disparos o pico de volumen. Nunca en los primeros 2 s ni en los últimos 2.5 s. | `CLIP_ZOOM=0` |
| Cámara lenta | 1.2 s a 0.5x sobre una explosión (GTA y Juegos). Los subtítulos se corren para seguir sincronizados. | `CLIP_SLOWMO=0` |
| Cámara del streamer | En el modo dividido busca el recuadro fijo de la webcam (cara pequeña en una esquina, zona que no cambia) y el panel de arriba muestra solo eso, sin pedazos del juego. Si no hay recuadro, usa el método anterior. | `CLIP_FACECAM=0` |
| GPU | Prueba NVIDIA, Intel, AMD o Mac al arrancar; si no hay o falla, usa CPU y el clip sale igual. | `CLIP_ENCODER=cpu` |
| Subtítulos por persona | Un color por persona hablando. **Solo si instalas pyannote y pones HF_TOKEN**; si no, salen como siempre. | `SUBS_PER_SPEAKER=0` |

Por tipo: GTA acción y Juegos = zoom + cámara lenta; GTA RP y Reality = solo zoom; Podcast, Entrevista y Directo = ninguno (se pueden forzar con `CLIP_ZOOM=1`).

## Limitaciones (dichas con franqueza)
- **No probé con tus videos ni con tu tarjeta.** Pruebas con audio, video y una webcam sintéticos. La GPU la probé solo en el camino de fallo (aquí no hay tarjeta): el código de NVIDIA/Intel/AMD/Mac está sin ejecutar en hardware real.
- **GPU: ganancia moderada.** Recorte, subtítulos y zoom siguen en el CPU; la GPU solo codifica. Y a igual bitrate la GPU suele verse un poco peor que x264. Si notas menos nitidez, `CLIP_ENCODER=cpu`.
- **Subtítulos por persona: no probé pyannote** (no está instalado aquí). Probé la asignación y los colores, no la diarización. Pesa ~2 GB.
- **Pitido:** depende de que Whisper escriba la palabra y la ubique bien; si la transcribe distinto ("cono" por "coño") no se pita. Agrégala en `BLEEP_WORDS`. Se pita por lista, no por significado.
- **Umbrales de zoom/cámara lenta sin calibrar** con tu gameplay (igual que en la Parte 3).
- **Tamaño de archivo:** el piso de 6 Mbps hace que un clip de más de ~80 s pase de 60 MB (hasta ~135 MB a 180 s). Si tu Storage limita a 50 MB por archivo, baja ese piso en `render._bitrate`.
- En la web no hay interruptores todavía (no pude compilar la web aquí): se controla con `.env`.

## Arreglado
- `test_framing.py` fallaba por dos pruebas viejas (bitrate de 44 MB/12 Mbps y el detector de scikit-image); actualizadas. El código estaba bien.

## Archivos
Nuevos: `postfx.py`, `encoder.py`, `speakers.py`, `test_parte4.py`. Cambiados: `render.py`, `framing.py`, `profiles.py`, `config.py`, `main.py`, `live.py`, `rerender.py`, `test_framing.py`, `.env.example`.
