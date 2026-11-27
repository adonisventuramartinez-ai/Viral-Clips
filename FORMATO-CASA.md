# 🏠 Formato "La Casa" (el que usaría un editor profesional)

## ¿Cuál es el mejor y por qué?

Para **La Casa de Alofoke** el formato correcto es **vertical 9:16 con la cara grande arriba y el mismo momento difuminado abajo** (`casa`), no el fondo difuminado puro ni el recorte vertical lleno.

| Formato | Qué pasa en un reality | Veredicto |
|---|---|---|
| `crop` (vertical lleno) | La IA sigue una cara, pero en una pelea con 3-4 personas se pierde quien responde y se corta el contexto del cuarto. | Bien para hablar solo, **no para drama**. |
| `blur` (video chico con fondo borroso) | Se ve la escena completa, pero la cara queda diminuta en el celular. El drama está en la mirada y el tono, no en el cuarto. | Bonito, **pero vende menos**. |
| `split` / `duo` | Pensados para cámara + gameplay o dos streamers. En la casa rompe la lectura. | No aplica. |
| **`casa`** | **Cara grande arriba (la IA sigue a quien habla) + el mismo tramo abajo con fondo oscuro y difuminado.** Se entiende quién dice qué, se ve la reacción y se mantiene el contexto. | **El formato de la casa.** |

Es el mismo criterio que usan los editores de realities: en 9:16 el primer plano manda; el cuarto se deja como textura, no como protagonista.

## Cómo quedó implementado

- **Perfil `reality`** (ya existente): drama, peleas, celos, nominaciones, español dominicano, `preroll` 3 s y `tail` 1.5 s para entrar antes del conflicto y cerrar en la reacción. `max_new` del directo **sigue en 3**.
- **Layout `casa` nuevo** en `worker/render.py`: panel superior de 1250 px con detección de cara (reutiliza `framing.py`) y panel inferior de 670 px con `boxblur`, brillo bajo y saturación baja. Todo en 1080x1920, 30 fps, CAS + nitidez y subtítulos por palabra.
- **Automático**: cuando el tipo de contenido es `reality` y no hay recuadro manual, el worker cambia `crop` → `casa`. No afecta a juegos, podcasts ni entrevistas.
- **Manual**: ya aparece como **"La Casa (reality)"** en `/crear`, **"La Casa de Alofoke..."** en `/en-vivo`, y **"🏠 La Casa"** en `/editor/[id]`. La vista previa del teléfono lo muestra igual.
- **Escape hatch**: pon `CLIP_REALITY_LAYOUT=crop` en `worker/.env` si quieres volver al vertical puro.

## Pruebas

- `test_formato_casa.py`: 8/8 (selección por perfil, respeto del recuadro manual, apagado por variable y grafo de ffmpeg con cara + difuminado).
- `test_autopiloto.py`: 14/14 (no se rompió el piloto).
- `test_parte13.py`: 14/14.
- `tsc --noEmit`: OK.

**Honestidad:** probé el grafo y la lógica, **no vi el render final con el video real de Alofoke**. Cuando prendas el directo, mira el primer clip: si la cara sale muy arriba o el difuminado muy oscuro, se ajustan dos números (`CASA_H` y `brightness`) sin tocar nada más.
