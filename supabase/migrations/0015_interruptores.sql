-- ClipForge · Parte 13 (botones de Clips automáticos y Cola automática en la web). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.
-- Una sola fila (id = 1). Cada interruptor vale:
--   true  = encendido desde la web
--   false = apagado desde la web
--   null  = nunca lo tocaste: manda lo que diga worker/.env (DISCOVER / AUTO_QUEUE), como hasta ahora
create table if not exists public.app_switches (
  id         int primary key check (id = 1),
  discover   boolean,
  auto_queue boolean,
  updated_at timestamptz not null default now()
);
insert into public.app_switches (id) values (1) on conflict (id) do nothing;
alter table public.app_switches enable row level security;
