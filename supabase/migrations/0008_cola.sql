-- ClipForge · Mejora 4 (cola con prioridades y reintentos). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- Prioridad: más alto se atiende antes (directos 10, ajustes de clip 5, videos 0)
alter table public.jobs add column if not exists priority int not null default 0;
-- No tomar el trabajo antes de esta hora (así se espera entre reintentos)
alter table public.jobs add column if not exists run_after timestamptz;
-- Máximo de intentos y último error técnico (para ver qué pasó)
alter table public.jobs add column if not exists max_attempts int not null default 3;
alter table public.jobs add column if not exists last_error text;
create index if not exists jobs_queue on public.jobs (status, priority desc, created_at);
