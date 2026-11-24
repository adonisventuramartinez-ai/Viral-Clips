# Calibración real del encuadre y subtítulos (con tus videos)

Ahora todos los parámetros se pueden ajustar en `worker/.env` sin tocar código.

El encuadre automático (`framing.py`) se probó solo con video sintético. Para que siga bien a la persona en tus videos reales, ajusta estas constantes en `worker/framing.py` (y/o en `worker/config.py`):

## 1. CLIP_FOCUS_X (config.py)
- 0.0 = persona a la izquierda, 0.5 = centro, 1.0 = derecha.
- Si el recorte siempre deja a la persona cortada por un lado, cambia este valor y prueba.

## 2. Detección de caras (framing.py)
- `DET_W` (default 720): sube a 960 si las caras son pequeñas/lejanas (más CPU).
- `MIN_COVERAGE` (0.2): si hay caras en menos del 20% del clip, se usa el centro. Sube si quieres ser más estricto.
- En `_raw_boxes`, `neigh=4` (luego 3): más bajo = detecta más caras (y más falsos positivos).

## 3. Movimiento de cámara (framing.py)
- `MIN_DWELL` (3): muestras seguidas antes de mover. Sube si la cámara se mueve demasiado; baja si reacciona lento.
- `MIN_GAP` (1.5): segundos mínimos entre paneos. Sube para evitar movimientos nerviosos.
- `URGENT_EDGE` (0.36): si la cara cae en el 14% exterior, reacciona rápido. Baja si reacciona muy tarde.
- `RAMP` (0.5): duración del paneo. Sube para más suave.
- `dead = 0.2 * crop_frac`: zona muerta (no mueve si el cambio es pequeño). Sube para menos movimiento.

## 4. Modo dividido (streamer facecam)
- `FACECAM_W` (960): ancho de análisis. Sube si la cámara del streamer es muy pequeña.
- En `facecam_pick`, `w <= 0.17` y `_in_corner`: ajusta si tu cámara es más grande o está en otra esquina.

## 5. Dos personas (duo)
- En `split_two`, `sep < max(0.18, fw * 1.8)`: separación mínima entre personas. Sube si mezcla a dos personas pegadas; baja si no detecta a dos.

## Cómo probar
1. Genera 3-5 clips con encuadre "Vertical" (crop) en videos reales.
2. Revisa si la persona queda centrada y si la cámara se mueve bien.
3. Ajusta una constante a la vez y vuelve a generar.
4. Si el encuadre se vuelve peor, revierte.

## Nota
Los cambios en `framing.py` requieren reconstruir el Docker del worker. Haz un clip de prueba antes y después de cada cambio.