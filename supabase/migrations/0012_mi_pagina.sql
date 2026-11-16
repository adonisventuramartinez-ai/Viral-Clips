-- ClipForge · Parte 10 (Mi página: estadísticas, mejores horas aprendidas y Facebook como fuente). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- Números de cada publicación (última lectura)
create table if not exists public.post_stats (
  network      text not null check (network in ('facebook','instagram','youtube')),
  external_id  text not null,
  post_id      uuid,
  clip_id      uuid references public.clips(id) on delete set null,
  published_at timestamptz,
  views        int not null default 0,
  likes        int not null default 0,
  comments     int not null default 0,
  shares       int not null default 0,
  error        text,
  fetched_at   timestamptz not null default now(),
  primary key (network, external_id)
);
create index if not exists post_stats_pub on public.post_stats (published_at desc);

-- Mejores horas aprendidas (hora local de tu país). network = 'all' junta todas las redes.
create table if not exists public.best_hours (
  network    text not null,
  slot       text not null,                -- 'HH:MM'
  score      numeric not null default 0,   -- 1.0 = tu promedio
  posts      int not null default 0,
  chosen     boolean not null default false,
  explore    boolean not null default false,
  updated_at timestamptz not null default now(),
  primary key (network, slot)
);

-- Seguidores por día (para ver cuánto crece tu página)
create table if not exists public.page_followers (
  network   text not null,
  day       date not null,
  followers int not null,
  primary key (network, day)
);

-- Facebook como fuente de clips automáticos
alter table public.discover_feeds drop constraint if exists discover_feeds_kind_check;
alter table public.discover_feeds add constraint discover_feeds_kind_check check (kind in ('channel','search','facebook'));

alter table public.post_stats enable row level security;
alter table public.best_hours enable row level security;
alter table public.page_followers enable row level security;
