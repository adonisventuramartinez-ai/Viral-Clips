// L├¡mite de intentos por IP y por tipo (login, registro). En memoria del servidor: frena la fuerza bruta casual
// (en Vercel hay varias instancias, as├¡ que no es un muro perfecto; para algo m├ís fuerte usa Vercel Firewall / Upstash).
const MAX_FAILS = Number(process.env.LOGIN_MAX_FAILS || 5);
const WINDOW_MS = Number(process.env.LOGIN_WINDOW_MIN || 15) * 60 * 1000;
const fails = new Map<string, { n: number; first: number }>();

export function clientIp(req: Request) {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return req.headers.get("x-real-ip") || "desconocida";
}

function prune(now: number) {
  if (fails.size < 500) return;
  for (const [k, f] of fails) if (now - f.first > WINDOW_MS) fails.delete(k);
}

/** Si ya se pas├│ del l├¡mite devuelve los segundos que faltan; si no, 0. */
export function blockedFor(key: string, now = Date.now()): number {
  prune(now);
  const rec = fails.get(key);
  if (rec && now - rec.first > WINDOW_MS) { fails.delete(key); return 0; }
  const cur = fails.get(key);
  return cur && cur.n >= MAX_FAILS ? Math.max(1, Math.ceil((cur.first + WINDOW_MS - now) / 1000)) : 0;
}

export function addFail(key: string, now = Date.now()) {
  const f = fails.get(key) || { n: 0, first: now };
  f.n += 1;
  fails.set(key, f);
}

export function clearFails(key: string) { fails.delete(key); }

export const tooMany = (secs: number) => `Demasiados intentos. Prueba otra vez en ${Math.ceil(secs / 60)} min.`;


// --- Funciones de rate limiting para Facebook (fb-web-publisher) ---
import { supabaseAdmin } from "@/lib/db";
import { NextRequest } from "next/server";


// Límite de peticiones respaldado por Postgres (función rl_hit, migración 005).
// En serverless no sirve un contador en memoria: cada petición puede caer en una
// instancia distinta. Aquí el contador es atómico y compartido.
//
// Si la función aún no existe o la BD falla, se PERMITE la petición (fail-open):
// un límite de ritmo nunca debe dejar a todos fuera de su propia app.

export function ipDe(req: NextRequest): string {
  const real = req.headers.get("x-real-ip");
  if (real) return real.trim();
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return "desconocida";
}

export async function permitido(clave: string, maximo: number, ventanaSegundos: number): Promise<boolean> {
  try {
    const { data, error } = await supabaseAdmin.rpc("rl_hit", {
      p_clave: clave,
      p_max: maximo,
      p_ventana_seg: ventanaSegundos,
    });
    if (error) return true;
    return data !== false;
  } catch {
    return true;
  }
}
