import { NextResponse } from "next/server";

export const runtime = "nodejs";

/** Salir: borra las dos cookies de sesión (la de cuenta y la de solo clave). */
export async function POST() {
  const res = NextResponse.json({ ok: true });
  for (const name of ["cf_session", "cf_auth"]) res.cookies.set(name, "", { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax", path: "/", maxAge: 0 });
  return res;
}
