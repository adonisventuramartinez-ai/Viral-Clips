-- ClipForge · TODO el SQL en un solo archivo (Partes 1 + 2).
-- Pégalo completo en Supabase > SQL Editor > New query y toca Run.
-- Se puede ejecutar más de una vez sin problema.

create extension if not exists "pgcrypto";

create table if not exists public.sources (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,
  kind         text not null check (kind in ('vod_url','upload','live')),
  url          text,
  storage_path text,
  title        text,
  range_from   text,
  range_to     text,
  status       text not null default 'queued',
  error        text,
  created_at   timestamptz not null default now()
);
-- estados válidos (incluye 'downloading' que usa el worker)
alter table public.sources drop constraint if exists sources_status_check;
alter table public.sources add constraint sources_status_check
  check (status in ('queued','downloading','recording','transcribing','analyzing','clipping','done','error','stopped'));

create table if not exists public.clips (
  id           uuid primary key default gen_random_uuid(),
  source_id    uuid not null references public.sources(id) on delete cascade,
  user_id      uuid references auth.users(id) on delete cascade,
  title        text not null,
  start_sec    numeric not null,
  end_sec      numeric not null,
  viral_score  int  not null check (viral_score between 0 and 100),
  reason       text,
  captions     jsonb,
  storage_path text,
  size_bytes   bigint,
  narrated     boolean not null default false,
  created_at   timestamptz not null default now()
);

create table if not exists public.rejected_moments (
  id         uuid primary key default gen_random_uuid(),
  source_id  uuid not null references public.sources(id) on delete cascade,
  title      text not null,
  score      int  not null,
  reason     text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id        bigint generated always as identity primary key,
  source_id uuid not null references public.sources(id) on delete cascade,
  at_sec    numeric not null,
  author    text,
  body      text not null
);
create index if not exists chat_messages_source_at on public.chat_messages (source_id, at_sec);

create table if not exists public.transcript_segments (
  id        bigint generated always as identity primary key,
  source_id uuid not null references public.sources(id) on delete cascade,
  start_sec numeric not null,
  end_sec   numeric not null,
  text      text not null
);
create index if not exists transcript_source_start on public.transcript_segments (source_id, start_sec);

create table if not exists public.jobs (
  id          uuid primary key default gen_random_uuid(),
  source_id   uuid not null references public.sources(id) on delete cascade,
  type        text not null check (type in ('download','record','transcribe','analyze','clip','narrate','summary')),
  payload     jsonb not null default '{}',
  status      text not null default 'queued' check (status in ('queued','running','done','error')),
  attempts    int not null default 0,
  locked_at   timestamptz,
  created_at  timestamptz not null default now()
);
create index if not exists jobs_status_created on public.jobs (status, created_at);

create table if not exists public.settings (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  clip_seconds   int  not null default 45,
  clips_per_run  int  not null default 15,
  quality        text not null default '1080p',
  style          text not null default 'viral',
  language       text not null default 'es',
  review_minutes int  not null default 2
);

-- Realtime (se ignora si ya estaban agregadas)
do $$
declare t text;
begin
  foreach t in array array['sources','clips','rejected_moments','jobs'] loop
    begin
      execute format('alter publication supabase_realtime add table public.%I', t);
    exception when duplicate_object then null;
    end;
  end loop;
end $$;

-- RLS activado. La app usa la service role key en el servidor, que salta RLS;
-- sin políticas, el acceso público con la anon key queda bloqueado.
alter table public.sources             enable row level security;
alter table public.clips               enable row level security;
alter table public.rejected_moments    enable row level security;
alter table public.chat_messages       enable row level security;
alter table public.transcript_segments enable row level security;
alter table public.jobs                enable row level security;
alter table public.settings            enable row level security;

drop policy if exists "own sources" on public.sources;
create policy "own sources" on public.sources for all using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own clips" on public.clips;
create policy "own clips" on public.clips for all using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own settings" on public.settings;
create policy "own settings" on public.settings for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Buckets privados de Storage
insert into storage.buckets (id, name, public) values
  ('uploads','uploads',false), ('recordings','recordings',false), ('clips','clips',false)
on conflict (id) do nothing;
