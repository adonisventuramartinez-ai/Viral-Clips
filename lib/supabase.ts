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
  return url && service ? createClient(url, service, { auth: { persistSession: false } }) : null;
}
