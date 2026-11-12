# Cambios de esta versión
- Duración hasta 90 s y calidad hasta 4K en Proyecto y En vivo (live.py entiende 1440p/2160p).
- En vivo ahora respeta el encuadre elegido (antes siempre salía vertical normal).
- Nueva página /clipeadores (el sidebar apuntaba a una página que no existía).
- setup_completo.sql ya incluye la migración 0004 (comunidad).
- /api/jobs valida link, tipo, duración, cantidad, calidad y encuadre.
- La IA ahora busca clips más cercanos a la duración pedida (0.75x–1.3x).
- Se borró la copia duplicada de la web en worker/, Nav.tsx y las cookies.

# Para desplegar
1. Supabase > SQL Editor: ejecuta supabase/migrations/0004_comunidad.sql (si no lo hiciste).
2. git add -A && git commit -m "mejoras" && git push origin main
3. Worker: docker build --no-cache -t clipforge-worker . y arráncalo otra vez.
4. Copia tu worker/.env desde tu PC (el zip va sin él, por seguridad).

# Segunda tanda
- Biblioteca: buscador por título, filtro por score, orden (virales/recientes/antiguos), contador y paso "X de 5" en trabajos activos.
- Cada clip: botón Público/Privado (controla si sale en el Top y el feed), "Copiar título + hashtags", y borrar sin recargar la página.
- /api/clips/[id]: ahora usa el cliente seguro (antes se rompía al compilar sin llaves) y tiene PATCH para público/título.
- Si aún no corriste la migración 0004, la Biblioteca sigue funcionando.

# Tercera tanda
- Nuevo encuadre "Dos personas": la IA detecta las dos caras solas; la de la izquierda va arriba y la de la derecha abajo (o la de más arriba, si están una sobre otra). Sin marcar nada a mano. Si no ve a dos, usa mitad izquierda arriba y mitad derecha abajo. Disponible en Proyecto y En vivo.
- Cantidad de clips: 15, 20, 30 y 50 (antes máx. 10). La IA pide más candidatos para poder llegar a la cantidad.
- Arreglo: dos caras en la misma columna se tomaban como una sola.
