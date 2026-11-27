import { NextResponse } from "next/server";
import { checkPassword, hashPassword } from "@/lib/password";
import { addFail, blockedFor, clearFails, tooMany } from "@/lib/rateLimit";
import { cleanName, validAvatar, validPassword } from "@/lib/profile";
import { currentUser } from "@/lib/session";
import { serverClient } from "@/lib/supabase";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const miss = (m: string) => (/accounts/i.test(m) ? "Falta correr 0016_cuentas.sql en Supabase" : m);

/** Mi cuenta: { user: { username, display_name, avatar } } o { user: null } si entraste solo con la clave de acceso. */
export async function GET(req: Request) {
  const username = await currentUser(req);
  const db = serverClient();
  if (!username || !db) return NextResponse.json({ user: null });
  const { data, error } = await db.from("accounts").select("username,display_name,avatar").eq("username", username).maybeSingle();
  if (error) return NextResponse.json({ user: null, error: miss(error.message) });
  return NextResponse.json({ user: data ?? null });
}

/** Cambiar mi cuenta. Cuerpo (todo opcional): { display_name, avatar (foto o null para quitarla), current_password + new_password }. */
export async function PATCH(req: Request) {
  const username = await currentUser(req);
  if (!username) return NextResponse.json({ error: "Entra con tu cuenta para cambiar el perfil" }, { status: 401 });
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const patch: Record<string, string | null> = {};

  if ("display_name" in b) {
    const n = cleanName(b.display_name);
    if (!n) return NextResponse.json({ error: "Escribe tu nombre (de 2 a 40 letras)" }, { status: 400 });
    patch.display_name = n;
  }
  if ("avatar" in b) {
    if (b.avatar !== null && !validAvatar(b.avatar)) return NextResponse.json({ error: "La foto no sirve: usa una imagen JPG, PNG o WebP" }, { status: 400 });
    patch.avatar = b.avatar;
  }
  if ("new_password" in b) {
    if (!validPassword(b.new_password)) return NextResponse.json({ error: "La contraseña nueva debe tener al menos 8 caracteres" }, { status: 400 });
    const key = `pw:${username}`;
    const wait = blockedFor(key);
    if (wait) return NextResponse.json({ error: tooMany(wait) }, { status: 429 });
    const { data, error } = await db.from("accounts").select("password_hash").eq("username", username).maybeSingle();
    if (error) return NextResponse.json({ error: miss(error.message) }, { status: 500 });
    if (!data || !(await checkPassword(typeof b.current_password === "string" ? b.current_password : "", data.password_hash))) {
      addFail(key);
      return NextResponse.json({ error: "La contraseña actual no es correcta" }, { status: 401 });
    }
    clearFails(key);
    patch.password_hash = await hashPassword(b.new_password);
  }
  if (!Object.keys(patch).length) return NextResponse.json({ error: "No mandaste ningún cambio" }, { status: 400 });

  const { data, error } = await db.from("accounts").update(patch).eq("username", username).select("username,display_name,avatar").maybeSingle();
  if (error) return NextResponse.json({ error: miss(error.message) }, { status: 500 });
  if (!data) return NextResponse.json({ error: "Esa cuenta ya no existe" }, { status: 404 });
  return NextResponse.json({ ok: true, user: data });
}
