-- ClipForge · comunidad. Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- 1) Columnas que la API y el worker ya usan
alter table public.sources add column if not exists layout text default 'crop';
alter table public.sources add column if not exists custom_crop jsonb;
alter table public.sources add column if not exists clipper text;
alter table public.clips   add column if not exists is_public boolean not null default true;
alter table public.clips   add column if not exists clipper text;

-- 2) Tablas
create table if not exists public.suggestions (
  id uuid primary key default gen_random_uuid(),
  author text, body text not null check (char_length(body) between 5 and 500),
  votes int not null default 0, created_at timestamptz not null default now());

create table if not exists public.donors (
  id uuid primary key default gen_random_uuid(),
  name text not null, amount numeric, message text, created_at timestamptz not null default now());

create table if not exists public.programs (
  id uuid primary key default gen_random_uuid(),
  name text not null, channel_url text, schedule text, created_at timestamptz not null default now());

create table if not exists public.social_accounts (
  id uuid primary key default gen_random_uuid(),
  clipper text not null, platform text not null check (platform in ('tiktok','instagram','youtube')),
  handle text not null, created_at timestamptz not null default now(),
  unique (clipper, platform));

-- 3) Contadores y ranking
create or replace function public.site_stats() returns json language sql stable as $$
  select json_build_object(
    'clips',    (select count(*) from public.clips),
    'creators', (select count(distinct clipper) from public.clips where clipper is not null),
    'users',    (select count(distinct clipper) from public.sources where clipper is not null));
$$;

create or replace function public.top_clippers(lim int default 20)
returns table (clipper text, clips bigint, best_score int, avg_score numeric) language sql stable as $$
  select clipper, count(*), max(viral_score), round(avg(viral_score),1)
  from public.clips where clipper is not null
  group by clipper order by count(*) desc, max(viral_score) desc limit lim;
$$;

-- 4) RLS (todo pasa por el servidor con la service role key)
alter table public.suggestions     enable row level security;
alter table public.donors          enable row level security;
alter table public.programs        enable row level security;
alter table public.social_accounts enable row level security;
