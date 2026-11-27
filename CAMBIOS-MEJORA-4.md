# Mejora 4: profesionalismo del producto

## Antes de usarla
1. Corre `supabase/migrations/0008_cola.sql` en Supabase > SQL Editor (sin esto todo funciona, pero sin prioridades ni espera entre reintentos).
2. Reinicia el worker.
3. Corre `npm run build` antes de subir la web (aquí solo revisé la lógica, no se compiló).

## Qué trae
- **Reintentos**: si un trabajo falla por internet, límite de la IA, memoria o ffmpeg, se repite solo (hasta 3 veces, esperando 1, 5 y 15 min). Si el error no se arregla solo (video borrado, cookies vencidas, sin voz) queda en error de una vez. Al reintentar se borran los clips a medias para no duplicar.
- **Errores en español**: la Biblioteca muestra qué pasó y qué hacer, no un texto técnico. El detalle técnico queda en el worker y en `jobs.last_error`.
- **Botón ↻ Reintentar** en cada fuente que falló (Biblioteca).
- **Prioridades**: directos (10) > ajustes de clip y vista previa (5-8) > videos (0).
- **Logs claros**: cada línea con hora y `[tipo id]`, tiempo por etapa y resumen al final. Se guardan en `worker/logs/worker.log` (rota solo).
- **Plantillas de marca**: Ajustes > Plantillas de marca. Guarda logo + subtítulos + gancho con nombre y elígelo en Crear clips.
- **Vista previa**: botón en Crear clips que muestra 1 cuadro real (encuadre, gancho, logo, subtítulos) sin crear los clips.

## Límites
- La vista previa no incluye la tarjeta de intro/cierre del Modo Original.
- Los directos no se reintentan (ya pasaron).
- Plantillas y vista previa necesitan internet en el worker (descarga ~8 s del video).
