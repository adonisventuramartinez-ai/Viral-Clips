-- ClipForge · Parte 8 (cola de publicación en Facebook, Instagram y YouTube). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.
create table if not exists public.posts (
  id           uuid primary key default gen_random_uuid(),
  clip_id      uuid not null references public.clips(id) on delete cascade,
  network      text not null check (network in ('facebook','instagram','youtube')),
  status       text not null default 'queued' check (status in ('queued','publishing','published','error','cancelled')),
  scheduled_at timestamptz not null,
  external_id  text,
  error        text,
  attempts     int not null default 0,
  published_at timestamptz,
  created_at   timestamptz not null default now(),
  unique (clip_id, network)
);
create index if not exists posts_due on public.posts (scheduled_at) where status = 'queued';
alter table public.posts enable row level security;
