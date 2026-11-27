# Cámara del en vivo — al máximo (2.0)

## Qué cambió

- **Captura del directo a 1080p como mínimo** (`LIVE_MIN_HEIGHT=1080`). Antes se grababa a 720p y el recorte 9:16 se estiraba a 1080: la cámara salía borrosa. Es `-c copy`, así que no cuesta CPU extra.
- **Detector de caras YuNet** (modelo `worker/cascades/face_detection_yunet_2023mar.onnx`, incluido). La imagen Docker trae OpenCV 5.1 sin `CascadeClassifier` ni los XML de Haar, y el código caía a scikit-image: **2.7 s por cuadro**. Ahora son ~0.05 s y ve caras de frente y de perfil, con gorra o lentes.
- **Seguimiento más preciso**: 3.5 muestras/s, análisis a 960 px, boca en vez de toda la cara para decidir quién habla, zona muerta del 7 %, paneo suave de 0.45 s y respaldo de perfiles cuando no ve a nadie.
- **Caras sentadas / abajo del cuadro**: antes se descartaban las que estuvieran por debajo del 75 % de la altura; ahora se aceptan hasta el 92 % (exigiendo proporción de cara, para no seguir botones ni textos).
- **Nitidez final**: `CAS` (pensado para recortes ampliados) + un toque de `unsharp`, en vez de un `unsharp` fuerte que dejaba halos.
- **Límite de 44 MB intacto** y sin tocar YouTube/Twitch/Kick.

## Ajustes rápidos en `worker/.env`

| Variable | Valor actual | Para qué sirve |
|---|---|---|
| `LIVE_MIN_HEIGHT` | `1080` | Piso de resolución al grabar el directo |
| `CLIP_CAM_DET_W` | `960` | Ancho del cuadro que se analiza busca caras |
| `CLIP_CAM_FPS` | `3.5` | Muestras por segundo para seguir a la persona |
| `CLIP_CAM_FACE_MIN` | `0.035` | Cara mínima que se considera |
| `CLIP_MIN_DWELL` | `3` | Muestras seguidas antes de cambiar de persona |
| `CLIP_MIN_GAP` | `3` | Segundos mínimos entre paneos (subir si se mueve mucho) |
| `CLIP_RAMP` | `0.55` | Duración del paneo (bajar si quieres más reacción) |
| `CLIP_CAS` | `0.65` | Nitidez CAS (0 = apagada) |
| `CLIP_SHARPEN` | `0.35` | Unsharp adicional (0 = apagado) |

Si el paneo te queda muy inquieto: `CLIP_MIN_GAP=4`. Si se queda mirando a quien ya no habla: `CLIP_MIN_DWELL=2` y `CLIP_RAMP=0.45`.

Después de cambiar `.env` o el código: doble clic en `INICIAR-DOCKER-LOCAL.bat` (reconstruye y reinicia el contenedor). Para ver estado: `VER-ESTADO-DOCKER.bat`.
