-- =====================================================================
-- Facebook 2.0 · pegar directo en Supabase → SQL Editor → New query → Run
-- =====================================================================
-- Crea (sin borrar nada) las tablas que usa la sección de Facebook y deja
-- el cron disparando /api/cron cada minuto desde Supabase (pg_cron + pg_net).
--
-- ANTES de pegar: sustituye __CRON_SECRET__ por el valor de CRON_SECRET de
-- Vercel. Ese mismo valor va en la variable CRON_SECRET del proyecto 2.0.
-- No compartas este archivo con el secreto rellenado.
-- =====================================================================

-- ---------- 1. Tablas ------------------------------------------------
create table if not exists public.usuarios_autorizados (
  fb_id            text primary key,
  nombre           text not null,
  codigo_solicitud text,
  estado           text not null default 'pendiente' check (estado in ('pendiente', 'aprobado', 'rechazado')),
  solicitado_en    timestamptz not null default now(),
  aprobado_en      timestamptz
);

create table if not exists public.cuentas_fb (
  id                 bigint generated always as identity primary key,
  nombre             text not null,
  token_encriptado   text not null,
  propietario_fb_id  text not null,
  creado_en          timestamptz not null default now()
);

create table if not exists public.posts_programados (
  id                 bigint generated always as identity primary key,
  cuenta_id          bigint references public.cuentas_fb (id) on delete set null,
  propietario_fb_id  text not null,
  paginas            jsonb not null default '[]'::jsonb,
  tipo               text not null check (tipo in ('foto', 'video', 'reel')),
  titulo             text,
  mensaje            text,
  archivo_url        text not null,
  archivo_nombre     text,
  fecha_programada   timestamptz not null,
  recurrencia        text not null default 'ninguna' check (recurrencia in ('ninguna', 'diaria', 'semanal')),
  estado             text not null default 'pendiente'
                       check (estado in ('pendiente', 'publicando', 'completado', 'error', 'cancelado')),
  intentos           int not null default 0,
  resultados         jsonb not null default '{}'::jsonb,
  ultimo_error       text,
  bloqueado_en       timestamptz,
  serie_id           bigint,
  creado_en          timestamptz not null default now()
);

create table if not exists public.plantillas (
  id                 bigint generated always as identity primary key,
  propietario_fb_id  text not null,
  nombre             text not null,
  titulo             text,
  mensaje            text,
  creado_en          timestamptz not null default now()
);

create table if not exists public.cron_latido (
  id          int primary key,
  ultimo      timestamptz,
  procesados  int
);
insert into public.cron_latido (id) values (1) on conflict (id) do nothing;

create table if not exists public.importaciones (
  id bigint generated always as identity primary key,
  propietario_fb_id text not null,
  tipo text not null check (tipo in ('video', 'perfil')),
  url text not null,
  estado text not null default 'pendiente'
    check (estado in ('pendiente', 'procesando', 'listo', 'error', 'usado')),
  titulo text, descripcion text, autor text, duracion int, bytes bigint,
  archivo_url text, miniatura_path text, videos jsonb, error text,
  creado_en timestamptz not null default now(),
  iniciado_en timestamptz, terminado_en timestamptz
);

create table if not exists public.rate_limit (
  clave           text primary key,
  intentos        int not null,
  ventana_inicio  timestamptz not null default now()
);

-- ---------- 2. Columnas nuevas --------------------------------------
alter table public.posts_programados add column if not exists fecha_original timestamptz;
alter table public.cuentas_fb        add column if not exists token_invalido_en timestamptz;
alter table public.cron_latido       add column if not exists ultima_limpieza timestamptz;

-- ---------- 3. Índices ----------------------------------------------
create index if not exists posts_pendientes_idx on public.posts_programados (fecha_programada) where estado = 'pendiente';
create index if not exists posts_publicando_idx on public.posts_programados (bloqueado_en) where estado = 'publicando';
create index if not exists posts_dueno_idx on public.posts_programados (propietario_fb_id, fecha_programada);
create index if not exists posts_archivo_idx on public.posts_programados (archivo_url);
create index if not exists posts_cuenta_idx on public.posts_programados (cuenta_id);
create unique index if not exists posts_serie_fecha_uq on public.posts_programados (serie_id, fecha_programada) where serie_id is not null;

create index if not exists cuentas_dueno_idx on public.cuentas_fb (propietario_fb_id);
create index if not exists plantillas_dueno_idx on public.plantillas (propietario_fb_id);
create index if not exists importaciones_dueno_idx on public.importaciones (propietario_fb_id, id desc);
create index if not exists importaciones_pendientes_idx on public.importaciones (estado) where estado in ('pendiente', 'procesando');

-- ---------- 4. Seguridad --------------------------------------------
do $$
declare t text;
begin
  foreach t in array array['usuarios_autorizados','cuentas_fb','posts_programados','plantillas','cron_latido','importaciones','rate_limit']
  loop
    execute format('alter table public.%I enable row level security', t);
    execute format('revoke all on table public.%I from anon, authenticated', t);
  end loop;
end $$;

-- ---------- 5. Storage privado --------------------------------------
insert into storage.buckets (id, name, public)
values ('archivos-programados', 'archivos-programados', false)
on conflict (id) do update set public = false;

-- ---------- 6. Límite de intentos -----------------------------------
create or replace function public.rl_hit(p_clave text, p_max int, p_ventana_seg int)
returns boolean
language plpgsql
security definer
set search_path = public
as $$
declare
  v_intentos int;
begin
  insert into public.rate_limit as r (clave, intentos, ventana_inicio)
  values (p_clave, 1, now())
  on conflict (clave) do update set
    intentos = case when r.ventana_inicio < now() - make_interval(secs => p_ventana_seg) then 1 else r.intentos + 1 end,
    ventana_inicio = case when r.ventana_inicio < now() - make_interval(secs => p_ventana_seg) then now() else r.ventana_inicio end
  returning intentos into v_intentos;
  return v_intentos <= p_max;
end;
$$;
revoke all on function public.rl_hit(text, int, int) from public, anon, authenticated;
grant execute on function public.rl_hit(text, int, int) to service_role;

-- ---------- 7. Cron desde Supabase (cada minuto) --------------------
create extension if not exists pg_cron;
create extension if not exists pg_net;
create extension if not exists supabase_vault with schema vault;

do $$
begin
  if exists (select 1 from vault.secrets where name = 'publicador_cron_secret') then
    perform vault.update_secret(
      (select id from vault.secrets where name = 'publicador_cron_secret' limit 1),
      '__CRON_SECRET__'
    );
  else
    perform vault.create_secret('__CRON_SECRET__', 'publicador_cron_secret', 'Bearer para /api/cron 2.0');
  end if;
end $$;

select cron.unschedule('publicador-cron-2-0')
where exists (select 1 from cron.job where jobname = 'publicador-cron-2-0');

select cron.schedule(
  'publicador-cron-2-0',
  '* * * * *',
  $$
  select net.http_get(
    url := 'https://viral-clip-2-0.vercel.app/api/cron',
    headers := jsonb_build_object(
      'Authorization', 'Bearer ' || (
        select decrypted_secret from vault.decrypted_secrets
        where name = 'publicador_cron_secret' limit 1
      )
    ),
    timeout_milliseconds := 58000
  );
  $$
);

-- Mantenimiento diario (03:10 UTC)
select cron.unschedule('publicador-mantenimiento-2-0')
where exists (select 1 from cron.job where jobname = 'publicador-mantenimiento-2-0');

select cron.schedule(
  'publicador-mantenimiento-2-0',
  '10 3 * * *',
  $$
  delete from public.rate_limit where ventana_inicio < now() - interval '1 day';
  delete from net._http_response where created < now() - interval '2 days';
  delete from cron.job_run_details where end_time < now() - interval '3 days';
  delete from public.posts_programados
   where estado in ('completado', 'cancelado') and fecha_programada < now() - interval '180 days';
  delete from public.importaciones
   where estado in ('usado', 'error') and creado_en < now() - interval '60 days';
  $$
);

-- Comprobar: select jobname, schedule from cron.job order by jobname;
