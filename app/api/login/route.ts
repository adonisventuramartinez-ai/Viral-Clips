import { NextResponse } from "next/server";
import { authToken, sessionSecret, signSession } from "@/lib/auth";
import { checkPassword, sameSecret } from "@/lib/password";
import { addFail, blockedFor, clearFails, clientIp, tooMany } from "@/lib/rateLimit";
import { cleanUsername } from "@/lib/profile";
import { cookieOpts } from "@/lib/session";
import { serverClient } from "@/lib/supabase";

export const runtime = "nodejs";

// Dos formas de entrar:
//  1) { username, password }  → tu cuenta (cookie cf_session, 30 días)
//  2) { password }            → solo la clave de acceso de la app (APP_PASSWORD), como antes; sirve de respaldo si no hay cuentas.
// Límite de intentos por IP: 5 fallos cada 15 minutos (ver lib/ratelimit.ts). Un acceso correcto borra los fallos de esa IP.
export async function POST(req: Request) {
  const key = `login:${clientIp(req)}`;
  const wait = blockedFor(key);
  if (wait) return NextResponse.json({ error: tooMany(wait) }, { status: 429, headers: { "Retry-After": String(wait) } });

  const b = await req.json().catch(() => ({}));
  const password = typeof b.password === "string" ? b.password : "";

  if (typeof b.username === "string" && b.username.trim()) {
    const db = serverClient();
    if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
    const username = cleanUsername(b.username);
    let row: { username: string; display_name: string; password_hash: string } | null = null;
    if (username) {
      const { data, error } = await db.from("accounts").select("username,display_name,password_hash").eq("username", username).maybeSingle();
      if (error) return NextResponse.json({ error: /accounts/i.test(error.message) ? "Falta correr 0016_cuentas.sql en Supabase" : error.message }, { status: 500 });
      row = data;
    }
    // Se verifica siempre (aunque el usuario no exista) para que no se note por el tiempo.
    const good = await checkPassword(password, row?.password_hash);
    if (!row || !good) {
      addFail(key);
      return NextResponse.json({ error: "Usuario o contraseña incorrectos" }, { status: 401 });
    }
    clearFails(key);
    await db.from("accounts").update({ last_login: new Date().toISOString() }).eq("username", row.username);
    const res = NextResponse.json({ ok: true, user: { username: row.username, display_name: row.display_name } });
    res.cookies.set("cf_session", await signSession(row.username, sessionSecret()), cookieOpts(30));
    return res;
  }

  const pw = process.env.APP_PASSWORD;
  if (!pw || !sameSecret(password, pw)) {
    addFail(key);
    return NextResponse.json({ error: "Contraseña incorrecta" }, { status: 401 });
  }
  clearFails(key);
  const res = NextResponse.json({ ok: true });
  res.cookies.set("cf_auth", await authToken(pw), cookieOpts(30));
  return res;
}
