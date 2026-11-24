-- ClipForge · Modo Transformar (Anti-Penalización)
-- Ejecútalo UNA VEZ en Supabase > SQL Editor si tu base ya estaba instalada.
-- Si instalas desde cero con setup_completo.sql, estos valores ya están incluidos.
-- Se puede correr varias veces sin problema (idempotente).

-- 0) Columnas: por si la base viene de una migración antigua que no las tiene.
alter table public.sources add column if not exists kind text not null default 'vod_url';
alter table public.jobs    add column if not exists type text not null default 'download';

-- 1) Quitamos CUALQUIER check antiguo sobre sources.kind (el nombre puede variar
-- según cómo se creó la tabla) y lo volvemos a crear con 'transform' incluido.
do $$
declare c text;
begin
  for c in
    select conname from pg_constraint
    where conrelid = 'public.sources'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) ilike '%(kind%'
  loop
    execute format('alter table public.sources drop constraint %I', c);
  end loop;

  alter table public.sources add constraint sources_kind_check
    check (kind in ('vod_url', 'upload', 'live', 'transform', 'text_to_video'));
end $$;

-- 2) Igual para jobs.type.
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
    check (type in ('download', 'record', 'transcribe', 'analyze', 'clip', 'narrate', 'summary', 'transform', 'text_to_video'));
end $$;

-- 3) El bucket 'uploads' ya lo crea setup_completo.sql. Esto solo lo asegura.
insert into storage.buckets (id, name, public)
  values ('uploads', 'uploads', false)
on conflict (id) do nothing;
