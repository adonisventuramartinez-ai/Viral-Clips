import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const service = process.env.SUPABASE_SERVICE_ROLE_KEY;

export const supabaseConfigured = Boolean(url && anon);

/** Cliente para el navegador (usa la anon key + RLS). */
export function browserClient(): SupabaseClient | null {
  return url && anon ? createClient(url, anon) : null;
}

/** Cliente de servidor (rutas /api). Salta RLS: nunca lo importes en componentes cliente. */
export function serverClient(): SupabaseClient | null {
  // SUPABASE_URL se lee al ejecutar (no se graba en el build como NEXT_PUBLIC_*), así que siempre es la actual.
  const serverUrl = process.env.SUPABASE_URL || url;
  if (!serverUrl || !service) return null;
  return createClient(serverUrl, service, {
    auth: { persistSession: false },
    // Next.js 14 guarda en caché los fetch del servidor y devolvía datos viejos (clips, cola, estado del worker).
    global: { fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }) },
  });
}
