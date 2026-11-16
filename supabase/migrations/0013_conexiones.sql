-- ClipForge · Conectar cuentas (Facebook, Instagram, YouTube) desde la web. Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.
-- Guarda las llaves de tus redes. Solo el servidor (service role) puede leerlas: la web nunca las devuelve completas.
create table if not exists public.connections (
  network    text primary key check (network in ('facebook','instagram','youtube')),
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.connections enable row level security;
