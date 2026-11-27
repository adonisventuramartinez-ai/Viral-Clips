import { createClient, SupabaseClient } from "@supabase/supabase-js";
import { limpiarEnv, urlSupabase } from "./env";

// Esta llave (anon/publishable) es SEGURA de exponer al navegador -
// es la que Supabase diseñó para esto. Nunca uses aquí la llave secreta.
//
// El cliente se crea de forma perezosa: antes se creaba al importar el módulo y
// `next build` fallaba con "supabaseUrl is required" si las variables
// NEXT_PUBLIC_SUPABASE_* aún no existían (p. ej. en un deploy de preview).
let cliente: SupabaseClient | null = null;

function crear(): SupabaseClient {
  const url = urlSupabase(process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL);
  const anon = limpiarEnv(
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  );
  if (!url || !anon) {
    throw new Error(
      "Faltan NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY en Vercel (y hay que volver a desplegar: las NEXT_PUBLIC_ se fijan al compilar)."
    );
  }
  return createClient(url, anon, { auth: { persistSession: false, autoRefreshToken: false } });
}

export const supabaseBrowser = new Proxy({} as SupabaseClient, {
  get(_t, prop) {
    if (!cliente) cliente = crear();
    const valor = (cliente as any)[prop];
    return typeof valor === "function" ? valor.bind(cliente) : valor;
  },
});

export const BUCKET = "archivos-programados";

