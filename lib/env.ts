// Utilidades para leer variables de entorno de forma tolerante a los errores de copiar/pegar
// más comunes en Vercel y GitHub: espacios o saltos de línea al final, comillas alrededor,
// URLs con "/" final o "/rest/v1", repositorio pegado como URL completa, etc.
// (Solo funciones puras: es seguro importarlo también desde código del navegador.)

/** Quita espacios/saltos de línea y comillas que rodean el valor. */
export function limpiarEnv(valor?: string | null): string {
  let s = (valor ?? "").trim();
  if (s.length >= 2 && ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'")))) {
    s = s.slice(1, -1).trim();
  }
  return s;
}

/** https://xxxx.supabase.co/  ·  https://xxxx.supabase.co/rest/v1/  →  https://xxxx.supabase.co */
export function urlSupabase(valor?: string | null): string {
  return limpiarEnv(valor).replace(/\/+$/, "").replace(/\/(rest|storage|auth)\/v1$/i, "").replace(/\/+$/, "");
}

/** "https://github.com/usuario/repo.git" o "usuario/repo/" → "usuario/repo" */
export function repoGithub(valor?: string | null): string {
  return limpiarEnv(valor)
    .replace(/^(https?:\/\/)?(www\.)?github\.com\//i, "")
    .replace(/\.git$/i, "")
    .replace(/^\/+|\/+$/g, "");
}

export type TipoLlaveSupabase = "secret" | "service_role" | "publishable" | "anon" | "desconocida";

/**
 * Dice qué tipo de llave de Supabase es, sin llamar a la red.
 * Error clásico: poner la llave pública (anon / publishable) donde va la SECRETA:
 * la app arranca, pero toda consulta falla con "permission denied" (la migración 005 revoca anon).
 */
export function tipoLlaveSupabase(llave?: string | null): TipoLlaveSupabase {
  const k = limpiarEnv(llave);
  if (k.startsWith("sb_secret_")) return "secret";
  if (k.startsWith("sb_publishable_")) return "publishable";
  const partes = k.split(".");
  if (partes.length === 3) {
    try {
      const b64 = partes[1].replace(/-/g, "+").replace(/_/g, "/");
      const json = JSON.parse(atob(b64 + "=".repeat((4 - (b64.length % 4)) % 4)));
      if (json?.role === "service_role") return "service_role";
      if (json?.role === "anon") return "anon";
    } catch {
      /* no es un JWT legible */
    }
  }
  return "desconocida";
}

export const esLlaveSecreta = (t: TipoLlaveSupabase) => t === "secret" || t === "service_role";

