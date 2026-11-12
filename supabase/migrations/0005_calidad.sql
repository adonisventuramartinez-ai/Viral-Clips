-- ClipForge · Parte 1 (calidad de clips). Ejecútalo en Supabase > SQL Editor. Se puede correr varias veces.

-- Opciones de cada fuente (tipo de contenido, juego, barra de progreso...). El botón "Ajustar" las reutiliza.
alter table public.sources add column if not exists options jsonb;

-- Descripción y hashtags que escribe la IA para cada clip (la web los usa al copiar para TikTok / Shorts / Reels)
alter table public.clips add column if not exists description text;
alter table public.clips add column if not exists hashtags text[];
