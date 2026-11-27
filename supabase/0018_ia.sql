-- ClipForge · Crear con IA (texto -> video 60 s)
-- Ejecútalo UNA VEZ si tu base ya existía antes de esta sección.
-- Si instalas desde cero con setup_completo.sql, ya está incluido. Idempotente.

-- 0) Por si se saltó 0017_transform.sql.
alter table public.sources add column if not exists kind text not null default 'vod_url';
alter table public.jobs    add column if not exists type text not null default 'download';

-- 1) sources.kind acepta 'text_to_video'.
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

-- 2) jobs.type acepta 'text_to_video'.
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

-- El prompt, el estilo y la música viajan en jobs.payload / sources.options (jsonb):
-- no hacen falta columnas nuevas.
