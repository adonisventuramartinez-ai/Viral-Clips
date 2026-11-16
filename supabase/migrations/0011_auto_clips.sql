-- ClipForge · Parte 9 (clips automáticos de lo mejor del momento). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.
create table if not exists public.discover_feeds (
  id           uuid primary key default gen_random_uuid(),
  name         text,
  kind         text not null default 'channel' check (kind in ('channel','search')),
  target       text not null,                    -- link del canal, o texto de búsqueda
  active       boolean not null default true,
  content_type text not null default 'auto',
  game         text,
  layout       text not null default 'crop',
  clips        int  not null default 4 check (clips between 1 and 15),
  quality      text not null default '720p',
  min_minutes  int  not null default 3,
  max_minutes  int  not null default 120,
  max_age_hours int not null default 48,
  min_views    int  not null default 0,
  clipper      text,
  last_checked timestamptz,
  last_status  text,
  created_at   timestamptz not null default now()
);
create table if not exists public.discovered_videos (
  id         uuid primary key default gen_random_uuid(),
  feed_id    uuid not null references public.discover_feeds(id) on delete cascade,
  video_id   text not null,
  title      text,
  url        text,
  views      int,
  status     text not null check (status in ('queued','skipped')),
  reason     text,
  source_id  uuid,
  created_at timestamptz not null default now(),
  unique (feed_id, video_id)
);
create index if not exists discovered_recent on public.discovered_videos (created_at desc);
alter table public.discover_feeds enable row level security;
alter table public.discovered_videos enable row level security;
