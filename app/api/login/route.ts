import { NextResponse } from "next/server";
import { createHash, timingSafeEqual } from "node:crypto";
import { authToken } from "@/lib/auth";

export const runtime = "nodejs";

// Límite de intentos por IP: 5 fallos cada 15 minutos. Se guarda en memoria del servidor, así que en
// Vercel (varias instancias) frena la fuerza bruta casual pero no es un muro perfecto; para algo más
// fuerte, pon Vercel Firewall / Upstash. Un login correcto borra los fallos de esa IP.
const MAX_FAILS = Number(process.env.LOGIN_MAX_FAILS || 5);
const WINDOW_MS = Number(process.env.LOGIN_WINDOW_MIN || 15) * 60 * 1000;
const fails = new Map<string, { n: number; first: number }>();

function clientIp(req: Request) {
  const xff = req.headers.get("x-forwarded-for");
  if (xff) return xff.split(",")[0].trim();
  return req.headers.get("x-real-ip") || "desconocida";
}

function sameSecret(a: string, b: string) {
  // se comparan los hashes (misma longitud siempre) en tiempo constante
  const ha = createHash("sha256").update(a).digest();
  const hb = createHash("sha256").update(b).digest();
  return timingSafeEqual(ha, hb);
}

function prune(now: number) {
  if (fails.size < 500) return;
  for (const [ip, f] of fails) if (now - f.first > WINDOW_MS) fails.delete(ip);
}

export async function POST(req: Request) {
  const now = Date.now();
  const ip = clientIp(req);
  prune(now);

  const rec = fails.get(ip);
  if (rec && now - rec.first > WINDOW_MS) fails.delete(ip);
  const cur = fails.get(ip);
  if (cur && cur.n >= MAX_FAILS) {
    const retry = Math.max(1, Math.ceil((cur.first + WINDOW_MS - now) / 1000));
    return NextResponse.json(
      { error: `Demasiados intentos. Prueba otra vez en ${Math.ceil(retry / 60)} min.` },
      { status: 429, headers: { "Retry-After": String(retry) } },
    );
  }

  const { password } = await req.json().catch(() => ({ password: "" }));
  const pw = process.env.APP_PASSWORD;
  if (!pw || typeof password !== "string" || !sameSecret(password, pw)) {
    const f = fails.get(ip) || { n: 0, first: now };
    f.n += 1;
    fails.set(ip, f);
    return NextResponse.json({ error: "Contraseña incorrecta" }, { status: 401 });
  }

  fails.delete(ip);
  const res = NextResponse.json({ ok: true });
  res.cookies.set("cf_auth", await authToken(pw), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return res;
}
