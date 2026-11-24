import { NextResponse } from "next/server";
import { sessionSecret, signSession } from "@/lib/auth";
import { hashPassword, sameSecret } from "@/lib/password";
import { addFail, blockedFor, clientIp, tooMany } from "@/lib/rateLimit";
import { MAX_ACCOUNTS, cleanName, cleanUsername, validPassword } from "@/lib/profile";
import { cookieOpts } from "@/lib/session";
import { serverClient } from "@/lib/supabase";

export const runtime = "nodejs";

/** Crear cuenta. Pide el código de acceso (la clave APP_PASSWORD de la app) para que nadie de afuera pueda registrarse.
 *  Cuerpo: { username, display_name, password, code }. Al crearla, ya entras. */
export async function POST(req: Request) {
  const key = `reg:${clientIp(req)}`;
  const wait = blockedFor(key);
  if (wait) return NextResponse.json({ error: tooMany(wait) }, { status: 429, headers: { "Retry-After": String(wait) } });

  const b = await req.json().catch(() => ({}));
  const pw = process.env.APP_PASSWORD;
  if (pw && !(typeof b.code === "string" && sameSecret(b.code, pw))) {
    addFail(key);
    return NextResponse.json({ error: "El código de acceso no es correcto" }, { status: 401 });
  }
  const username = cleanUsername(b.username);
  const name = cleanName(b.display_name);
  if (!username) return NextResponse.json({ error: "El usuario debe tener de 3 a 24 letras minúsculas, números, punto o guion bajo" }, { status: 400 });
  if (!name) return NextResponse.json({ error: "Escribe tu nombre (de 2 a 40 letras)" }, { status: 400 });
  if (!validPassword(b.password)) return NextResponse.json({ error: "La contraseña debe tener al menos 8 caracteres" }, { status: 400 });

  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const miss = (m: string) => (/accounts/i.test(m) ? "Falta correr 0016_cuentas.sql en Supabase" : m);
  const { count, error: e0 } = await db.from("accounts").select("id", { count: "exact", head: true });
  if (e0) return NextResponse.json({ error: miss(e0.message) }, { status: 500 });
  if ((count ?? 0) >= MAX_ACCOUNTS) return NextResponse.json({ error: `Máximo ${MAX_ACCOUNTS} cuentas` }, { status: 400 });

  const { error } = await db.from("accounts").insert({ username, display_name: name, password_hash: await hashPassword(b.password), last_login: new Date().toISOString() });
  if (error) {
    if (error.code === "23505" || /duplicate|unique/i.test(error.message)) return NextResponse.json({ error: "Ese usuario ya existe, prueba otro" }, { status: 409 });
    return NextResponse.json({ error: miss(error.message) }, { status: 500 });
  }
  const res = NextResponse.json({ ok: true, user: { username, display_name: name } });
  res.cookies.set("cf_session", await signSession(username, sessionSecret()), cookieOpts(30));
  return res;
}
