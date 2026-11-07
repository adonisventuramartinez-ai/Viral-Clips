-- Parte 2: el worker usa el estado 'downloading'. Ejecútalo en SQL Editor.
alter table public.sources drop constraint if exists sources_status_check;
alter table public.sources add constraint sources_status_check
  check (status in ('queued','downloading','recording','transcribing','analyzing','clipping','done','error','stopped'));
