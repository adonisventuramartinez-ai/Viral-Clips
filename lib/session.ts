import { sessionSecret, verifySession } from "@/lib/auth";

/** Usuario de la cuenta que hizo la petición (cookie cf_session), o null si entró solo con la clave de acceso. */
export async function currentUser(req: Request): Promise<string | null> {
  const m = /(?:^|;\s*)cf_session=([^;]+)/.exec(req.headers.get("cookie") || "");
  if (!m) return null;
  let v = m[1];
  try { v = decodeURIComponent(v); } catch {}
  return verifySession(v, sessionSecret());
}

/** Opciones de la cookie de sesión (solo servidor, no se lee desde JavaScript). */
export const cookieOpts = (days: number) => ({
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: 60 * 60 * 24 * days,
});
