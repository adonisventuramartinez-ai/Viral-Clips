# Mejora 1: encuadre, tarjetas, dramómetro y logo

Es un **parche**: copia estas carpetas encima de tu proyecto (te pedirá reemplazar; di que sí). No toca tu `.env` ni tus cookies. Sin SQL nuevo.

## Qué cambió
- **Encuadre (`worker/framing.py`)**
  - La cámara reacciona más rápido: ~1 s en vez de ~1.3 s, y ~0.7 s si la persona queda casi cortada en el borde.
  - Un cuadro suelto con ruido ya no mueve la cámara (mediana de 3 muestras).
  - Mejor detección en escenas oscuras (CLAHE) y un segundo intento menos estricto si no ve a nadie.
  - Si a OpenCV le faltan los archivos .xml, cae solo al detector de scikit-image en vez de no detectar nada.
- **Tarjeta de arriba (hook) y de cierre (`worker/original.py`)**
  - El fondo ya no es plano: usa el primer/último cuadro del clip, borroso y con movimiento lento.
  - Texto más grande (92 pt) con animación de entrada, y la voz narradora un poco más rápida.
  - La tarjeta de entrada dura 2.2 s como mínimo (antes 2.5); si hay voz, dura lo que dure la voz.
- **Dramómetro**: 580 px de ancho, centrado y bajo la zona del teléfono; el color cambia (amarillo < 50, naranja 50-74, rojo ≥ 75) y dura 5 s.
- **Logo (`worker/render.py`)**: nunca se coloca dentro de la zona segura (170 px arriba, 240 px abajo). Nueva posición **Automática** (arriba a la izquierda, lejos de la cara, el micrófono y los subtítulos). Está en Ajustes > Marca.

## Pruebas
`python test_framing_extra.py` (4) y todas las anteriores siguen pasando (Partes 1, 5, 6, calidad, encuadre).

## Pendiente / límites
- Probé el encuadre con datos sintéticos y con la imagen de prueba de scikit-image, **no con tu video fuente completo**. Mándame el video largo de WorldCast y lo calibro.
- La web no se compiló aquí: corre `npm run build` antes de subir (solo cambié una lista de opciones en `app/ajustes/page.tsx` y `app/api/brand/route.ts`).
- Si ya tenías el logo en "Abajo a la derecha", se subirá solo hasta la zona segura; elige "Automática" si quieres que se aparte del micrófono.
