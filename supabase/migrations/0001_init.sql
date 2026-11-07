-- ClipForge · esquema inicial
-- Pégalo en Supabase > SQL Editor y ejecútalo.

create extension if not exists "pgcrypto";

-- Fuente: un video/directo del que salen clips
create table public.sources (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,
  kind         text not null check (kind in ('vod_url','upload','live')),
  url          text,
  storage_path text,                       -- archivo subido o grabación en Storage
  title        text,
  range_from   text,                       -- "1:30:00"
  range_to     text,                       -- "2:30:00"
  status       text not null default 'queued'
               check (status in ('queued','recording','transcribing','analyzing','clipping','done','error','stopped')),
  error        text,
  created_at   timestamptz not null default now()
);

-- Clips generados
create table public.clips (
  id           uuid primary key default gen_random_uuid(),
  source_id    uuid not null references public.sources(id) on delete cascade,
  user_id      uuid references auth.users(id) on delete cascade,
  title        text not null,
  start_sec    numeric not null,
  end_sec      numeric not null,
  viral_score  int  not null check (viral_score between 0 and 100),
  reason       text,                       -- por qué la IA lo eligió
  captions     jsonb,                      -- palabras con timestamps para subtítulos
  storage_path text,                       -- mp4 vertical final
  size_bytes   bigint,
  narrated     boolean not null default false,
  created_at   timestamptz not null default now()
);

-- Momentos descartados ("Por qué no se eligieron")
create table public.rejected_moments (
  id         uuid primary key default gen_random_uuid(),
  source_id  uuid not null references public.sources(id) on delete cascade,
  title      text not null,
  score      int  not null,
  reason     text not null,
  created_at timestamptz not null default now()
);

-- Chat del directo (señal de viralidad)
create table public.chat_messages (
  id        bigint generated always as identity primary key,
  source_id uuid not null references public.sources(id) on delete cascade,
  at_sec    numeric not null,
  author    text,
  body      text not null
);
create index on public.chat_messages (source_id, at_sec);

-- Progreso de transcripción por segmentos
create table public.transcript_segments (
  id        bigint generated always as identity primary key,
  source_id uuid not null references public.sources(id) on delete cascade,
  start_sec numeric not null,
  end_sec   numeric not null,
  text      text not null
);
create index on public.transcript_segments (source_id, start_sec);

-- Cola de trabajos: el worker (Parte 2) los toma de aquí
create table public.jobs (
  id          uuid primary key default gen_random_uuid(),
  source_id   uuid not null references public.sources(id) on delete cascade,
  type        text not null check (type in ('download','record','transcribe','analyze','clip','narrate','summary')),
  payload     jsonb not null default '{}',
  status      text not null default 'queued' check (status in ('queued','running','done','error')),
  attempts    int not null default 0,
  locked_at   timestamptz,
  created_at  timestamptz not null default now()
);
create index on public.jobs (status, created_at);

-- Ajustes de IA por usuario
create table public.settings (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  clip_seconds   int  not null default 45,
  clips_per_run  int  not null default 15,
  quality        text not null default '1080p',
  style          text not null default 'viral',
  language       text not null default 'es',
  review_minutes int  not null default 2   -- cada cuánto revisa en modo En vivo
);

-- Realtime para que la pestaña En vivo se actualice sola
alter publication supabase_realtime add table public.sources, public.clips, public.rejected_moments, public.jobs;

-- RLS: cada usuario ve solo lo suyo
alter table public.sources          enable row level security;
alter table public.clips            enable row level security;
alter table public.rejected_moments enable row level security;
alter table public.chat_messages    enable row level security;
alter table public.transcript_segments enable row level security;
alter table public.jobs             enable row level security;
alter table public.settings         enable row level security;

create policy "own sources"  on public.sources  for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own clips"    on public.clips    for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own settings" on public.settings for all using (user_id = auth.uid()) with check (user_id = auth.uid());
create policy "own rejected" on public.rejected_moments for select
  using (exists (select 1 from public.sources s where s.id = source_id and s.user_id = auth.uid()));
create policy "own chat" on public.chat_messages for select
  using (exists (select 1 from public.sources s where s.id = source_id and s.user_id = auth.uid()));
create policy "own transcript" on public.transcript_segments for select
  using (exists (select 1 from public.sources s where s.id = source_id and s.user_id = auth.uid()));
create policy "own jobs" on public.jobs for select
  using (exists (select 1 from public.sources s where s.id = source_id and s.user_id = auth.uid()));

-- Storage: buckets privados
insert into storage.buckets (id, name, public) values
  ('uploads','uploads',false), ('recordings','recordings',false), ('clips','clips',false)
on conflict do nothing;
