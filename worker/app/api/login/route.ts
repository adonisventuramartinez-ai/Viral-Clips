import { NextResponse } from "next/server";
import { authToken } from "@/lib/auth";

export async function POST(req: Request) {
  const { password } = await req.json().catch(() => ({ password: "" }));
  const pw = process.env.APP_PASSWORD;
  if (!pw || password !== pw) return NextResponse.json({ error: "Contraseña incorrecta" }, { status: 401 });

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
