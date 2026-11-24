import { NextRequest, NextResponse } from "next/server";
import { GRAPH_BASE, appUrl, fbAppId, fbAppSecret } from "@/lib/graph";

// Esta función corre en el servidor. Es la ÚNICA que usa el APP_SECRET.
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const { searchParams, origin } = new URL(req.url);
  const baseUrl = appUrl(origin);

  const code = searchParams.get("code");
  const error = searchParams.get("error_description") || searchParams.get("error");
  const state = searchParams.get("state");
  const stateEsperado = req.cookies.get("fb_oauth_state")?.value;

  const volver = (ruta: string) => {
    const r = NextResponse.redirect(`${baseUrl}${ruta}`);
    r.cookies.set("fb_oauth_state", "", { path: "/", maxAge: 0 });
    return r;
  };

  if (error) return volver(`/facebook?error=${encodeURIComponent(error)}`);
  if (!code) return volver(`/facebook?error=${encodeURIComponent("No se recibió el código de autorización")}`);

  // Anti-CSRF: el state que mandamos a Facebook tiene que coincidir con el de la cookie
  if (!state || !stateEsperado || state !== stateEsperado) {
    return volver(`/facebook?error=${encodeURIComponent("Sesión de login inválida o expirada. Intenta de nuevo.")}`);
  }

  const APP_ID = fbAppId();
  const APP_SECRET = fbAppSecret();
  const REDIRECT_URI = `${baseUrl}/api/fb/auth/callback`;

  if (!APP_ID || !APP_SECRET) {
    return volver(`/facebook?error=${encodeURIComponent("Faltan FB_APP_ID / FB_APP_SECRET en las variables de entorno de Vercel")}`);
  }

  try {
    // 1) code → token de corta duración
    const tokenRes = await fetch(
      `${GRAPH_BASE}/oauth/access_token` +
        `?client_id=${APP_ID}` +
        `&client_secret=${APP_SECRET}` +
        `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}` +
        `&code=${encodeURIComponent(code)}`
    );
    const tokenData = await tokenRes.json();
    if (tokenData.error) throw new Error(tokenData.error.message || "Error al obtener el token");
    if (!tokenData.access_token) throw new Error("No se recibió access_token de Facebook");

    // 2) → token de larga duración (~60 días)
    const longRes = await fetch(
      `${GRAPH_BASE}/oauth/access_token` +
        `?grant_type=fb_exchange_token` +
        `&client_id=${APP_ID}` +
        `&client_secret=${APP_SECRET}` +
        `&fb_exchange_token=${encodeURIComponent(tokenData.access_token)}`
    );
    const longData = await longRes.json();
    const finalToken = longData.access_token || tokenData.access_token;
    if (!finalToken) throw new Error("No se pudo obtener el token final de Facebook");

    // 3) Se entrega en el fragmento (#) de la URL: no se envía a ningún servidor.
    // Se codifica para evitar problemas con caracteres especiales del token.
    return volver(`/facebook#token=${encodeURIComponent(finalToken)}`);
  } catch (err: any) {
    return volver(`/facebook?error=${encodeURIComponent(err.message)}`);
  }
}

