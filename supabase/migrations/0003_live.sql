-- Parte 4: modo En vivo + estado del worker. Ejecútalo en SQL Editor (se puede correr varias veces).
alter table public.sources add column if not exists stop_requested boolean not null default false;
alter table public.sources add column if not exists progress jsonb not null default '{}'::jsonb;

create table if not exists public.worker_status (
  id      int primary key default 1,
  seen_at timestamptz not null default now(),
  info    jsonb not null default '{}'::jsonb,
  constraint worker_status_single check (id = 1)
);
alter table public.worker_status enable row level security;
insert into public.worker_status (id) values (1) on conflict do nothing;
