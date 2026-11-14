# Parte 2: perfiles por tipo de contenido y largo ideal (sin Telegram)

Tipos nuevos (web y worker): **Reality (Casa de Alofoke)**, **GTA 5 acción**, **GTA RP**; Podcast y Entrevista ajustados.

| Tipo | Largo ideal | Qué prioriza |
|---|---|---|
| Reality | 45 s | peleas, discusiones, traiciones, chisme; arranca justo antes del conflicto; usa el elenco (`CAST_NAMES`) |
| GTA acción | 25 s | tiroteos, persecuciones, explosiones, reacciones; volumen pesa más que el cambio de imagen |
| GTA RP | 40 s | diálogo y actuación, escenas con remate; sin marcas de acción |
| Podcast / Entrevista | 75 s | opiniones fuertes, confesiones; la entrevista arranca en la pregunta |
| Juegos | 30 s | acción en pantalla |

- Duración **"Automática (según el tipo)"** (nuevo valor 0) en Crear clips, En vivo y Canales automáticos. Si eliges un número, se respeta.
- Palabras clave sin importar tildes ni mayúsculas.
- GTA sabe el juego sin que lo escribas.
- Pruebas: `python test_parte2.py`.
No hace falta correr SQL nuevo.
