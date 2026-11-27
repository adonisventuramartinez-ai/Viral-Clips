# Apertura al máximo (Original, Transformar y en vivo)

Problema: el intro no enganchaba. En **Transformar** se ponía una tarjeta narrada de ~2 s ANTES del video
(`TRANSFORM_INTRO=card`), y sobre el clip no se quemaba ningún gancho: la gente se iba antes de ver nada.
En **Original** el gancho dependía de lo que escribiera la IA y a veces caía en "MIRA ESTO".

## Qué cambió

- **Transformar arranca en frío** (`TRANSFORM_INTRO=cold`): el video entra en el cuadro 0 con el gancho
  amarillo arriba y el contexto debajo. La voz propia se **mezcla sobre el video** (`ffmpeg amix`), sin
  tarjeta previa. Se mantiene el aporte propio (voz, dramómetro, encuesta) y el límite de 44 MB.
- **Gancho afilado** (`hook.py`):
  - Se descartan ganchos genéricos ("MIRA ESTO", "INCREÍBLE", ...) y se saca uno de la propia transcripción.
  - Si el gancho es plano, se convierte en **duda abierta** ("¿Qué dijo que dejó a todos callados?"),
    sin inventar hechos ni spoilear. Si ya tiene impacto, se deja intacto.
  - `¿Sabes lo que pasó?` ya no se recorta como muletilla: es un gancho válido.
  - El inicio se mueve a la frase fuerte con los topes de `.env` (`HOOK_MAX_SHIFT`, `HOOK_MIN_GAIN`),
    que antes estaban fijos en el código y no se usaban.
- **Original**: el gancho siempre se afila, aunque no se mueva el inicio; el gancho se pinta amarillo sobre
  caja oscura (antes blanco sobre blanco) y se mantiene el dramómetro + contexto.
- **En vivo**: los clips del directo también pasan por `best_hook`, con el mismo filtro anti-genéricos.
- La IA del Modo Original ahora devuelve también un campo `hook` (4–8 palabras) y se valida antes de usarse.

## Ajustes en `worker/.env`

| Variable | Valor | Para qué |
|---|---|---|
| `TRANSFORM_INTRO` | `cold` | Arranca con video; `card` reactiva la tarjeta antigua (no recomendado) |
| `INTRO_MODE` | `cold` | Igual para el flujo Original |
| `SMART_START` | `1` | Mover el inicio a la frase fuerte |
| `HOOK_MAX_SHIFT` | `6` | Máximos segundos que se puede mover el inicio |
| `HOOK_MIN_GAIN` | `10` | Ganancia mínima para moverlo |
| `CLIP_HOOK_SIZE` | `72` | Tamaño del gancho en pantalla |

Si el gancho se siente muy grande en móvil: `CLIP_HOOK_SIZE=64`. Si quieres que el inicio se mueva más:
`HOOK_MAX_SHIFT=8`.

## Verificación

- `test_gancho.py` (29 comprobaciones), `test_apertura.py` (16) y `test_original2.py` (38) pasan dentro del contenedor.
- Render real de 38.5 s: 1080×1920, H.264 + AAC, 40.9 MB (bajo el tope de 44 MB), con el gancho
  visible desde el primer cuadro.
