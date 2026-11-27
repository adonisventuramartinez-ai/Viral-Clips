-- ClipForge Â· TODO el SQL en un solo archivo (Partes 1 + 2).
-- PÃ©galo completo en Supabase > SQL Editor > New query y toca Run.
-- Se puede ejecutar mÃ¡s de una vez sin problema.

create extension if not exists "pgcrypto";

create table if not exists public.sources (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references auth.users(id) on delete cascade,
  kind         text not null check (kind in ('vod_url','upload','live','transform','text_to_video')),
  url          text,
  storage_path text,
  title        text,
  range_from   text,
  range_to     text,
  status       text not null default 'queued',
  error        text,
  created_at   timestamptz not null default now()
);
-- estados vÃ¡lidos (incluye 'downloading' que usa el worker)
alter table public.sources drop constraint if exists sources_status_check;
alter table public.sources add constraint sources_status_check
  check (status in ('queued','downloading','recording','transcribing','analyzing','clipping','done','error','stopped'));

-- ===== 0003 en vivo (progreso y estado del worker) =====
-- La web lee sources.progress en /en-vivo y /api/preview, y /api/health revisa stop_requested.
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

create table if not exists public.clips (
  id           uuid primary key default gen_random_uuid(),
  source_id    uuid not null references public.sources(id) on delete cascade,
  user_id      uuid references auth.users(id) on delete cascade,
  title        text not null,
  start_sec    numeric not null,
  end_sec      numeric not null,
  viral_score  int  not null check (viral_score between 0 and 100),
  reason       text,
  captions     jsonb,
  storage_path text,
  size_bytes   bigint,
  narrated     boolean not null default false,
  created_at   timestamptz not null default now()
);

create table if not exists public.rejected_moments (
  id         uuid primary key default gen_random_uuid(),
  source_id  uuid not null references public.sources(id) on delete cascade,
  title      text not null,
  score      int  not null,
  reason     text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.chat_messages (
  id        bigint generated always as identity primary key,
  source_id uuid not null references public.sources(id) on delete cascade,
  at_sec    numeric not null,
  author    text,
  body      text not null
);
create index if not exists chat_messages_source_at on public.chat_messages (source_id, at_sec);

create table if not exists public.transcript_segments (
  id        bigint generated always as identity primary key,
  source_id uuid not null references public.sources(id) on delete cascade,
  start_sec numeric not null,
  end_sec   numeric not null,
  text      text not null
);
create index if not exists transcript_source_start on public.transcript_segments (source_id, start_sec);

create table if not exists public.jobs (
  id          uuid primary key default gen_random_uuid(),
  source_id   uuid not null references public.sources(id) on delete cascade,
  type        text not null check (type in ('download','record','transcribe','analyze','clip','narrate','summary','transform','text_to_video')),
  payload     jsonb not null default '{}',
  status      text not null default 'queued' check (status in ('queued','running','done','error')),
  attempts    int not null default 0,
  locked_at   timestamptz,
  created_at  timestamptz not null default now()
);
create index if not exists jobs_status_created on public.jobs (status, created_at);

create table if not exists public.settings (
  user_id        uuid primary key references auth.users(id) on delete cascade,
  clip_seconds   int  not null default 45,
  clips_per_run  int  not null default 15,
  quality        text not null default '1080p',
  style          text not null default 'viral',
  language       text not null default 'es',
  review_minutes int  not null default 2
);

-- Realtime (se ignora si ya estaban agregadas)
do $$
declare t text;
begin
  foreach t in array array['sources','clips','rejected_moments','jobs'] loop
    begin
      execute format('alter publication supabase_realtime add table public.%I', t);
    exception when duplicate_object then null;
    end;
  end loop;
end $$;

-- RLS activado. La app usa la service role key en el servidor, que salta RLS;
-- sin polÃ­ticas, el acceso pÃºblico con la anon key queda bloqueado.
alter table public.sources             enable row level security;
alter table public.clips               enable row level security;
alter table public.rejected_moments    enable row level security;
alter table public.chat_messages       enable row level security;
alter table public.transcript_segments enable row level security;
alter table public.jobs                enable row level security;
alter table public.settings            enable row level security;

drop policy if exists "own sources" on public.sources;
create policy "own sources" on public.sources for all using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own clips" on public.clips;
create policy "own clips" on public.clips for all using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "own settings" on public.settings;
create policy "own settings" on public.settings for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- Buckets privados de Storage
insert into storage.buckets (id, name, public) values
  ('uploads','uploads',false), ('recordings','recordings',false), ('clips','clips',false)
on conflict (id) do nothing;

-- ===== 0004 comunidad =====
-- ClipForge Â· comunidad. EjecÃºtalo en Supabase > SQL Editor. Se puede correr varias veces.

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

-- ===== 0005 calidad =====

-- Opciones de cada fuente (tipo de contenido, juego, barra de progreso...). El botÃ³n "Ajustar" las reutiliza.
alter table public.sources add column if not exists options jsonb;

-- DescripciÃ³n y hashtags que escribe la IA para cada clip (la web los usa al copiar para TikTok / Shorts / Reels)
alter table public.clips add column if not exists description text;
alter table public.clips add column if not exists hashtags text[];

-- ===== 0006 en vivo =====
create table if not exists public.live_commands (
  id         uuid primary key default gen_random_uuid(),
  source_id  uuid not null references public.sources(id) on delete cascade,
  kind       text not null default 'clip_now',
  seconds    int  not null default 45 check (seconds between 15 and 120),
  status     text not null default 'pending' check (status in ('pending','done','error')),
  message    text,
  clip_id    uuid,
  created_at timestamptz not null default now(),
  done_at    timestamptz
);
create index if not exists live_commands_pending on public.live_commands (source_id, status, created_at);
alter table public.live_commands enable row level security;

-- 2) Canales automÃ¡ticos: el worker mira cada pocos minutos si entraron en vivo y empieza a grabar solo
create table if not exists public.watch_channels (
  id             uuid primary key default gen_random_uuid(),
  name           text,
  url            text not null,
  active         boolean not null default true,
  content_type   text not null default 'auto',
  game           text,
  layout         text not null default 'crop',
  clip_seconds   int  not null default 45,
  quality        text not null default '720p',
  review_minutes int  not null default 2,
  max_new        int  not null default 3,
  progress_bar   boolean not null default false,
  clipper        text,
  last_video_id  text,
  last_checked   timestamptz,
  last_status    text,
  created_at     timestamptz not null default now()
);
alter table public.watch_channels enable row level security;

-- ===== 0007 publicaciÃ³n =====
-- ClipForge Â· Mejora 3 (paquete de publicaciÃ³n, miniatura, programaciÃ³n). EjecÃºtalo en Supabase > SQL Editor. Se puede correr varias veces.

-- Paquete que escribe la IA para cada clip: textos por red (TikTok, Reels/Facebook, Shorts), 3 ganchos alternativos y comentario fijado
alter table public.clips add column if not exists pack jsonb;
-- Miniatura (JPG vertical) guardada en el bucket "clips"
alter table public.clips add column if not exists thumb_path text;
-- ProgramaciÃ³n: el worker publica el clip en tu pÃ¡gina de Facebook cuando llega la hora
alter table public.clips add column if not exists scheduled_at timestamptz;
alter table public.clips add column if not exists publish_status text check (publish_status in ('scheduled','published','error'));
alter table public.clips add column if not exists publish_error text;
alter table public.clips add column if not exists fb_video_id text;
alter table public.clips add column if not exists published_at timestamptz;
create index if not exists clips_scheduled on public.clips (scheduled_at) where publish_status = 'scheduled';

-- ===== 0008 cola (prioridades y reintentos) =====
-- El worker necesita estas columnas para elegir trabajos y reintentar; antes faltaban en este archivo.
alter table public.jobs add column if not exists priority int not null default 0;
alter table public.jobs add column if not exists run_after timestamptz;
alter table public.jobs add column if not exists max_attempts int not null default 3;
alter table public.jobs add column if not exists last_error text;
create index if not exists jobs_queue on public.jobs (status, priority desc, created_at);

-- ===== 0009 viral =====
-- ClipForge Â· Parte 7 (Ã¡rea "Hacerlo viral"). EjecÃºtalo en Supabase > SQL Editor. Se puede correr varias veces.

-- AnÃ¡lisis viral de cada clip: puntaje, veredicto, mejor tÃ­tulo y alternativas, hashtags, texto de miniatura, riesgos
alter table public.clips add column if not exists viral jsonb;
-- pending = falta analizar | ready = listo para publicar | review = mÃ­ralo tÃº | rejected = descartado | approved = lo aprobaste tÃº
alter table public.clips add column if not exists viral_status text check (viral_status in ('pending','ready','review','rejected','approved'));
-- Segunda miniatura para probar A/B
alter table public.clips add column if not exists thumb_b_path text;
-- Los clips NUEVOS nacen "pending" (los viejos quedan sin estado y no se tocan)
alter table public.clips alter column viral_status set default 'pending';
create index if not exists clips_viral_status on public.clips (viral_status) where viral_status in ('pending','ready');

-- ===== 0010 cola de publicaciÃ³n =====
-- ClipForge Â· Parte 8 (cola de publicaciÃ³n en Facebook, Instagram y YouTube). EjecÃºtalo en Supabase > SQL Editor. Se puede correr varias veces.
create table if not exists public.posts (
  id           uuid primary key default gen_random_uuid(),
  clip_id      uuid not null references public.clips(id) on delete cascade,
  network      text not null check (network in ('facebook','instagram','youtube') or network ~ '^facebook:[0-9]+$'),
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

-- ===== 0011 clips automÃ¡ticos =====
-- ClipForge Â· Parte 9 (clips automÃ¡ticos de lo mejor del momento). EjecÃºtalo en Supabase > SQL Editor. Se puede correr varias veces.
create table if not exists public.discover_feeds (
  id           uuid primary key default gen_random_uuid(),
  name         text,
  kind         text not null default 'channel' check (kind in ('channel','search')),
  target       text not null,                    -- link del canal, o texto de bÃºsqueda
  active       boolean not null default true,
  content_type text not null default 'auto',
  game         text,
  layout       text not null default 'crop',
  clips        int  not null default 4 check (clips between 1 and 15),
  quality      text not null default '720p',
  min_minutes  int  not null default 3,
  max_minutes  int  not null default 120,
  max_age_hours int not null default 48,
  min_views    int  not null default 0,
  clipper      text,
  last_checked timestamptz,
  last_status  text,
  created_at   timestamptz not null default now()
);
create table if not exists public.discovered_videos (
  id         uuid primary key default gen_random_uuid(),
  feed_id    uuid not null references public.discover_feeds(id) on delete cascade,
  video_id   text not null,
  title      text,
  url        text,
  views      int,
  status     text not null check (status in ('queued','skipped')),
  reason     text,
  source_id  uuid,
  created_at timestamptz not null default now(),
  unique (feed_id, video_id)
);
create index if not exists discovered_recent on public.discovered_videos (created_at desc);
alter table public.discover_feeds enable row level security;
alter table public.discovered_videos enable row level security;

-- ===== 0012 mi pÃ¡gina =====

-- NÃºmeros de cada publicaciÃ³n (Ãºltima lectura)
create table if not exists public.post_stats (
  network      text not null check (network in ('facebook','instagram','youtube') or network ~ '^facebook:[0-9]+$'),
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

-- Mejores horas aprendidas (hora local de tu paÃ­s). network = 'all' junta todas las redes.
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

-- Seguidores por dÃ­a (para ver cuÃ¡nto crece tu pÃ¡gina)
create table if not exists public.page_followers (
  network   text not null,
  day       date not null,
  followers int not null,
  primary key (network, day)
);

-- Facebook como fuente de clips automÃ¡ticos
alter table public.discover_feeds drop constraint if exists discover_feeds_kind_check;
alter table public.discover_feeds add constraint discover_feeds_kind_check check (kind in ('channel','search','facebook'));

alter table public.post_stats enable row level security;
alter table public.best_hours enable row level security;
alter table public.page_followers enable row level security;

-- ===== 0013 conexiones =====
-- Guarda las llaves de tus redes. Solo el servidor (service role) puede leerlas: la web nunca las devuelve completas.
create table if not exists public.connections (
  network    text primary key check (network in ('facebook','instagram','youtube','autopilot')),
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.connections enable row level security;

-- ===== 0014 hacerlo viral =====

-- Pedido que la web le deja al worker sobre un clip: {"action":"thumbs"|"reanalyze", ...}. El worker lo atiende y lo borra.
-- Si falla, queda {"error":"motivo"} para que la web lo muestre.
alter table public.clips add column if not exists viral_req jsonb;
-- CuÃ¡l miniatura se usa al publicar: a (principal) o b (la de prueba)
alter table public.clips add column if not exists thumb_choice text check (thumb_choice in ('a','b'));

-- Ajustes de la pÃ¡gina Hacerlo viral (una sola fila, id = 1)
create table if not exists public.viral_config (
  id               int primary key check (id = 1),
  require_approval boolean not null default false,   -- true: nada entra a la cola sin que tÃº lo apruebes en Hacerlo viral
  updated_at       timestamptz not null default now()
);
insert into public.viral_config (id) values (1) on conflict (id) do nothing;
alter table public.viral_config enable row level security;

create index if not exists clips_viral_req on public.clips (created_at) where viral_req is not null;

-- ===== 0015 botones (clips automÃ¡ticos y cola) =====

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

-- ===== 0016 cuentas =====

-- Solo el servidor (service role) puede leer esta tabla: la web nunca devuelve contraseÃ±as ni la lista de cuentas.
create table if not exists public.accounts (
  id            uuid primary key default gen_random_uuid(),
  username      text not null unique check (username ~ '^[a-z0-9_.]{3,24}$'),
  display_name  text not null check (char_length(display_name) between 2 and 40),
  password_hash text not null,                     -- scrypt$sal$hash (nunca la contraseÃ±a)
  avatar        text,                              -- foto de perfil ya achicada (data:image/jpeg;base64,...)
  created_at    timestamptz not null default now(),
  last_login    timestamptz
);
alter table public.accounts enable row level security;


-- ClipForge 2.0 Â· Buscador de clips virales en TikTok / Instagram Reels.
-- EjecÃºtalo en Supabase > SQL Editor. Se puede correr varias veces.

-- 0) Los trabajos de bÃºsqueda no tienen una fuente de video: source_id puede ser null.
alter table public.jobs alter column source_id drop not null;

-- 1) El worker necesita un tipo de trabajo nuevo: 'search'.
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
    check (type in ('download','record','transcribe','analyze','clip','narrate','summary','transform','text_to_video','search'));
end $$;

-- 2) Una bÃºsqueda = lo que pidiÃ³ la persona + lo que encontrÃ³ el worker.
create table if not exists public.clip_searches (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users(id) on delete cascade,
  query         text,
  networks      text[] not null default array['tiktok','instagram'],
  accounts      text[] not null default '{}',
  links         text[] not null default '{}',
  min_views     int not null default 10000,
  max_age_hours int not null default 72,
  max_results   int not null default 10,
  auto_queue    int not null default 5,
  content_type  text not null default 'auto',
  publish_fb    boolean not null default true,
  status        text not null default 'queued' check (status in ('queued','running','done','error')),
  found         int not null default 0,
  queued        int not null default 0,
  error         text,
  created_at    timestamptz not null default now(),
  finished_at   timestamptz
);

create table if not exists public.clip_search_results (
  id         uuid primary key default gen_random_uuid(),
  search_id  uuid not null references public.clip_searches(id) on delete cascade,
  network    text not null check (network in ('tiktok','instagram')),
  video_id   text not null,
  url        text,
  title      text,
  views      int not null default 0,
  likes      int not null default 0,
  comments   int not null default 0,
  duration   int not null default 0,
  posted_at  timestamptz,
  score      int not null default 0,
  velocity   numeric not null default 0,
  status     text not null default 'found' check (status in ('found','queued','skipped','rejected')),
  reason     text,
  source_id  uuid references public.sources(id) on delete set null,
  created_at timestamptz not null default now(),
  unique (search_id, network, video_id)
);

create index if not exists clip_search_results_rank on public.clip_search_results (search_id, score desc);
create index if not exists clip_searches_recent on public.clip_searches (created_at desc);

alter table public.clip_searches enable row level security;
alter table public.clip_search_results enable row level security;

-- ===== BUSCADOR: RLS + PERMISOS =====
alter table public.clip_searches disable row level security;
alter table public.clip_search_results disable row level security;
GRANT ALL ON public.clip_searches TO service_role;
GRANT ALL ON public.clip_search_results TO service_role;
GRANT ALL ON public.clip_searches TO anon;
GRANT ALL ON public.clip_search_results TO anon;