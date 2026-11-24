import { NextRequest, NextResponse } from "next/server";
import { COOKIE_ADMIN, COOKIE_USUARIO, Sesion, verificarSesion } from "@/lib/fbSession";
import { supabaseAdmin } from "@/lib/db";

// El middleware ya bloquea las rutas protegidas; estas funciones se usan
// además dentro de cada ruta para saber QUIÉN es el dueño (defensa en profundidad).

// --- Revocación: una cookie firmada vale 7 días, pero si el admin rechaza a un
// usuario NO debe seguir entrando hasta que caduque. Se consulta la BD directamente
// (sin caché) para que los cambios de aprobación se reflejen inmediatamente.
async function usuarioSigueAprobado(fbId: string): Promise<boolean> {
  try {
    const { data, error } = await supabaseAdmin
      .from("usuarios_autorizados")
      .select("estado")
      .eq("fb_id", fbId)
      .maybeSingle();
    if (error) return true; // si la BD falla momentáneamente no dejamos a todos fuera: la firma ya es válida
    return data?.estado === "aprobado";
  } catch {
    return true;
  }
}

export async function sesionDe(req: NextRequest): Promise<Sesion | null> {
  const s = await verificarSesion(req.cookies.get(COOKIE_USUARIO)?.value);
  if (!s || s.rol !== "usuario") return null;
  return (await usuarioSigueAprobado(s.sub)) ? s : null;
}

export async function adminDe(req: NextRequest): Promise<Sesion | null> {
  const s = await verificarSesion(req.cookies.get(COOKIE_ADMIN)?.value);
  return s && s.rol === "admin" ? s : null;
}

export function noAutorizado() {
  return NextResponse.json({ error: "No autorizado" }, { status: 401 });
}

export function opcionesCookie(maxAgeSegundos: number) {
  return {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    maxAge: maxAgeSegundos,
    path: "/",
  };
}
