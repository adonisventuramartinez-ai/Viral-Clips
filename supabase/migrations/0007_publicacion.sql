-- ClipForge · Mejora 3 (paquete de publicación, miniatura, programación). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- Paquete que escribe la IA para cada clip: textos por red (TikTok, Reels/Facebook, Shorts), 3 ganchos alternativos y comentario fijado
alter table public.clips add column if not exists pack jsonb;
-- Miniatura (JPG vertical) guardada en el bucket "clips"
alter table public.clips add column if not exists thumb_path text;
-- Programación: el worker publica el clip en tu página de Facebook cuando llega la hora
alter table public.clips add column if not exists scheduled_at timestamptz;
alter table public.clips add column if not exists publish_status text check (publish_status in ('scheduled','published','error'));
alter table public.clips add column if not exists publish_error text;
alter table public.clips add column if not exists fb_video_id text;
alter table public.clips add column if not exists published_at timestamptz;
create index if not exists clips_scheduled on public.clips (scheduled_at) where publish_status = 'scheduled';
