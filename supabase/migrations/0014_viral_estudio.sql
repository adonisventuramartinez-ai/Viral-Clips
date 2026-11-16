-- ClipForge · Parte 12 (página "Hacerlo viral"). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- Pedido que la web le deja al worker sobre un clip: {"action":"thumbs"|"reanalyze", ...}. El worker lo atiende y lo borra.
-- Si falla, queda {"error":"motivo"} para que la web lo muestre.
alter table public.clips add column if not exists viral_req jsonb;
-- Cuál miniatura se usa al publicar: a (principal) o b (la de prueba)
alter table public.clips add column if not exists thumb_choice text check (thumb_choice in ('a','b'));

-- Ajustes de la página Hacerlo viral (una sola fila, id = 1)
create table if not exists public.viral_config (
  id               int primary key check (id = 1),
  require_approval boolean not null default false,   -- true: nada entra a la cola sin que tú lo apruebes en Hacerlo viral
  updated_at       timestamptz not null default now()
);
insert into public.viral_config (id) values (1) on conflict (id) do nothing;
alter table public.viral_config enable row level security;

create index if not exists clips_viral_req on public.clips (created_at) where viral_req is not null;
