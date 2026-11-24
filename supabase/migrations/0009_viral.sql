-- ClipForge · Parte 7 (área "Hacerlo viral"). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- Análisis viral de cada clip: puntaje, veredicto, mejor título y alternativas, hashtags, texto de miniatura, riesgos
alter table public.clips add column if not exists viral jsonb;
-- pending = falta analizar | ready = listo para publicar | review = míralo tú | rejected = descartado | approved = lo aprobaste tú
alter table public.clips add column if not exists viral_status text check (viral_status in ('pending','ready','review','rejected','approved'));
-- Segunda miniatura para probar A/B
alter table public.clips add column if not exists thumb_b_path text;
-- Los clips NUEVOS nacen "pending" (los viejos quedan sin estado y no se tocan)
alter table public.clips alter column viral_status set default 'pending';
create index if not exists clips_viral_status on public.clips (viral_status) where viral_status in ('pending','ready');
