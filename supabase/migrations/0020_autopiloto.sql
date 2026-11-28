DO $$
-- Piloto automático: abre los CHECK de connections/posts para 'autopilot' y 'facebook:<id>'.
-- Se puede correr varias veces. No toca datos existentes.
DECLARE
  c record;
BEGIN
  FOR c IN
    SELECT conname FROM pg_constraint AS pc
    WHERE pc.conrelid = 'public.connections'::regclass
      AND pc.contype = 'c'
      AND pg_get_constraintdef(pc.oid) ILIKE '%network%'
  LOOP
    EXECUTE format('ALTER TABLE public.connections DROP CONSTRAINT %I', c.conname);
  END LOOP;

  FOR c IN
    SELECT conname FROM pg_constraint AS pc
    WHERE pc.conrelid = 'public.posts'::regclass
      AND pc.contype = 'c'
      AND pg_get_constraintdef(pc.oid) ILIKE '%network%'
  LOOP
    EXECUTE format('ALTER TABLE public.posts DROP CONSTRAINT %I', c.conname);
  END LOOP;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.connections'::regclass AND conname = 'connections_network_check') THEN
    ALTER TABLE public.connections ADD CONSTRAINT connections_network_check
      CHECK (network IN ('facebook','instagram','youtube','autopilot'));
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'public.posts'::regclass AND conname = 'posts_network_check') THEN
    ALTER TABLE public.posts ADD CONSTRAINT posts_network_check
      CHECK (network IN ('facebook','instagram','youtube') OR network ~ '^facebook:[0-9]+$');
  END IF;
END $$;

-- La tabla puede existir sin la fila: el panel la crea al encender el piloto.
INSERT INTO public.connections (network, data)
VALUES ('autopilot', '{"enabled": false, "page_ids": [], "auto_approve": true, "max_per_run": 5}'::jsonb)
ON CONFLICT (network) DO NOTHING;
