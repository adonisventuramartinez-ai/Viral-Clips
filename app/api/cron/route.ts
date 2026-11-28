// El cron de Supabase (pg_cron) y el programador por lotes llaman a /api/cron.
// La implementación vive en /api/fb/cron; este alias evita duplicar lógica.
export * from "../fb/cron/route";
