import { NextResponse, type NextRequest } from "next/server";
import { authToken } from "@/lib/auth";

// Protege toda la app con una contraseña (variable APP_PASSWORD).
// Importante: las rutas /api usan la service role key, así que NO deben quedar abiertas al público.
export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  const pw = process.env.APP_PASSWORD;

  if (!pw) {
    if (process.env.NODE_ENV === "production") {
      return new NextResponse("Falta definir la variable APP_PASSWORD en Vercel (Settings > Environment Variables) y volver a desplegar.", { status: 503 });
    }
    return NextResponse.next(); // en tu PC (desarrollo) pasa sin contraseña
  }

  if (pathname === "/login" || pathname === "/api/login") return NextResponse.next();

  const cookie = req.cookies.get("cf_auth")?.value;
  if (cookie && cookie === (await authToken(pw))) return NextResponse.next();

  if (pathname.startsWith("/api/")) return NextResponse.json({ error: "No autorizado" }, { status: 401 });
  const url = req.nextUrl.clone();
  url.pathname = "/login";
  return NextResponse.redirect(url);
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
