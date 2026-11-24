-- ClipForge · Parte 14 (cuentas con usuario, nombre y foto de perfil). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.
-- Solo el servidor (service role) puede leer esta tabla: la web nunca devuelve contraseñas ni la lista de cuentas.
create table if not exists public.accounts (
  id            uuid primary key default gen_random_uuid(),
  username      text not null unique check (username ~ '^[a-z0-9_.]{3,24}$'),
  display_name  text not null check (char_length(display_name) between 2 and 40),
  password_hash text not null,                     -- scrypt$sal$hash (nunca la contraseña)
  avatar        text,                              -- foto de perfil ya achicada (data:image/jpeg;base64,...)
  created_at    timestamptz not null default now(),
  last_login    timestamptz
);
alter table public.accounts enable row level security;
