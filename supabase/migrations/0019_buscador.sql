alter table public.jobs alter column source_id drop not null;
-- 0) Los trabajos de búsqueda no tienen una fuente de video: source_id puede ser null.
-- Buscador de clips virales. Se puede correr varias veces.

-- 1) El worker necesita un tipo de trabajo nuevo: 'search'.
do $$
declare c text;
begin
  for c in
    select conname from pg_constraint
    where conrelid = 'public.jobs'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%(type%'
  loop
    execute format('alter table public.jobs drop constraint %I', c);
  end loop;

  alter table public.jobs add constraint jobs_type_check
    check (type in ('download','record','transcribe','analyze','clip','narrate','summary','transform','text_to_video','search'));
end $$;

-- 2) Una búsqueda = lo que pidió la persona + lo que encontró el worker.
create table if not exists public.clip_searches (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users(id) on delete cascade,
  query         text,
  networks      text[] not null default array['tiktok','instagram'],
  accounts      text[] not null default '{}',
  links         text[] not null default '{}',
  min_views     int not null default 10000,
  max_age_hours int not null default 72,
  max_results   int not null default 10,
  auto_queue    int not null default 5,
  content_type  text not null default 'auto',
  publish_fb    boolean not null default true,
  status        text not null default 'queued' check (status in ('queued','running','done','error')),
  found         int not null default 0,
  queued        int not null default 0,
  error         text,
  created_at    timestamptz not null default now(),
  finished_at   timestamptz
);

create table if not exists public.clip_search_results (
  id         uuid primary key default gen_random_uuid(),
  search_id  uuid not null references public.clip_searches(id) on delete cascade,
  network    text not null check (network in ('tiktok','instagram')),
  video_id   text not null,
  url        text,
  title      text,
  views      int not null default 0,
  likes      int not null default 0,
  comments   int not null default 0,
  duration   int not null default 0,
  posted_at  timestamptz,
  score      int not null default 0,
  velocity   numeric not null default 0,
  status     text not null default 'found' check (status in ('found','queued','skipped','rejected')),
  reason     text,
  source_id  uuid references public.sources(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (search_id, network, video_id)
);

create index if not exists clip_search_results_rank on public.clip_search_results (search_id, score desc);
create index if not exists clip_searches_recent on public.clip_searches (created_at desc);

alter table public.clip_searches enable row level security;
alter table public.clip_search_results enable row level security;
