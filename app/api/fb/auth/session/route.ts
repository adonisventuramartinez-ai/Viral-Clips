import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { supabaseAdmin } from "@/lib/db";
import { GRAPH_BASE, fbAppId, fbAppSecret } from "@/lib/graph";
import { COOKIE_USUARIO, firmarSesion, verificarSesion } from "@/lib/fbSession";
import { opcionesCookie } from "@/lib/fbAuth";
import { ipDe, permitido } from "@/lib/rateLimit";

export const dynamic = "force-dynamic";

const DIAS_SESION = 7;

// POST { token }  →  verifica el token de Facebook EN EL SERVIDOR, registra o
// recupera la solicitud de acceso y, si el usuario está aprobado, emite la
// cookie de sesión. Reemplaza a los antiguos /api/acceso/* (que aceptaban un
// fb_id sin verificar, así que cualquiera podía suplantar a otro usuario).
export async function POST(req: NextRequest) {
  try {
    // Cada intento llama a Facebook (debug_token): se limita por IP para que nadie lo use de martillo
    if (!(await permitido(`sesion:${ipDe(req)}`, 60, 300))) {
      return NextResponse.json({ error: "Demasiados intentos. Espera un momento." }, { status: 429 });
    }
    const { token } = await req.json();
    if (!token || typeof token !== "string") {
      return NextResponse.json({ estado: "sin_login", error: "Falta token" }, { status: 400 });
    }

    // 1) El token tiene que ser válido Y emitido para NUESTRA app
    const appToken = `${fbAppId()}|${fbAppSecret()}`;
    const dbgRes = await fetch(
      `${GRAPH_BASE}/debug_token?input_token=${encodeURIComponent(token)}&access_token=${encodeURIComponent(appToken)}`
    );
    const dbg = (await dbgRes.json())?.data;
    if (!dbg?.is_valid || String(dbg.app_id) !== fbAppId() || !dbg.user_id) {
      return NextResponse.json({ estado: "sin_login" }, { status: 401 });
    }
    const fbId: string = String(dbg.user_id);

    const meRes = await fetch(`${GRAPH_BASE}/me?fields=name&access_token=${encodeURIComponent(token)}`);
    const me = await meRes.json();
    const nombre: string = me?.name || "Usuario";

    // 2) ¿Existe ya una solicitud?
    let { data: usuario } = await supabaseAdmin
      .from("usuarios_autorizados")
      .select("estado, codigo_solicitud")
      .eq("fb_id", fbId)
      .maybeSingle();

    if (!usuario) {
      const codigo = crypto.randomInt(100000, 1000000).toString();
      const { error } = await supabaseAdmin
        .from("usuarios_autorizados")
        .insert({ fb_id: fbId, nombre, codigo_solicitud: codigo, estado: "pendiente" });
      if (error && error.code !== "23505") throw error; // 23505 = otra petición lo creó a la vez
      const rel = await supabaseAdmin
        .from("usuarios_autorizados")
        .select("estado, codigo_solicitud")
        .eq("fb_id", fbId)
        .single();
      usuario = rel.data;
    }

    const res = NextResponse.json({
      estado: usuario?.estado ?? "pendiente",
      codigo_solicitud: usuario?.codigo_solicitud ?? null,
      nombre,
      fb_id: fbId,
    });

    // 3) Solo los aprobados reciben cookie de sesión
    if (usuario?.estado === "aprobado") {
      const valor = await firmarSesion({ sub: fbId, nombre, rol: "usuario" }, DIAS_SESION * 86400);
      res.cookies.set(COOKIE_USUARIO, valor, opcionesCookie(DIAS_SESION * 86400));
    } else {
      res.cookies.set(COOKIE_USUARIO, "", opcionesCookie(0));
    }
    return res;
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al crear la sesión" }, { status: 500 });
  }
}

// GET → ¿hay sesión válida?
export async function GET(req: NextRequest) {
  const s = await verificarSesion(req.cookies.get(COOKIE_USUARIO)?.value);
  if (!s || s.rol !== "usuario") return NextResponse.json({ autenticado: false });
  return NextResponse.json({ autenticado: true, nombre: s.nombre, fb_id: s.sub });
}

// DELETE → cerrar sesión
export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_USUARIO, "", opcionesCookie(0));
  return res;
}

