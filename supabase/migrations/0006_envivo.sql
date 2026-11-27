-- ClipForge · Parte 2 (modo en vivo). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- 1) Botón "Clip ahora": la web deja un pedido y el worker lo corta con los últimos segundos del directo
create table if not exists public.live_commands (
  id         uuid primary key default gen_random_uuid(),
  source_id  uuid not null references public.sources(id) on delete cascade,
  kind       text not null default 'clip_now',
  seconds    int  not null default 45 check (seconds between 15 and 120),
  status     text not null default 'pending' check (status in ('pending','done','error')),
  message    text,
  clip_id    uuid,
  created_at timestamptz not null default now(),
  done_at    timestamptz
);
create index if not exists live_commands_pending on public.live_commands (source_id, status, created_at);
alter table public.live_commands enable row level security;

-- 2) Canales automáticos: el worker mira cada pocos minutos si entraron en vivo y empieza a grabar solo
create table if not exists public.watch_channels (
  id             uuid primary key default gen_random_uuid(),
  name           text,
  url            text not null,
  active         boolean not null default true,
  content_type   text not null default 'auto',
  game           text,
  layout         text not null default 'crop',
  clip_seconds   int  not null default 45,
  quality        text not null default '720p',
  review_minutes int  not null default 2,
  max_new        int  not null default 3,
  progress_bar   boolean not null default false,
  clipper        text,
  last_video_id  text,
  last_checked   timestamptz,
  last_status    text,
  created_at     timestamptz not null default now()
);
alter table public.watch_channels enable row level security;
