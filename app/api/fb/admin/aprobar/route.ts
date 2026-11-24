import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { adminDe, noAutorizado } from "@/lib/fbAuth";

export async function POST(req: NextRequest) {
  if (!(await adminDe(req))) return noAutorizado();

  const { fb_id, accion } = await req.json();
  if (!fb_id || !["aprobar", "rechazar"].includes(accion)) {
    return NextResponse.json({ error: "Datos inválidos" }, { status: 400 });
  }

  const nuevoEstado = accion === "aprobar" ? "aprobado" : "rechazado";

  const { error } = await supabaseAdmin
    .from("usuarios_autorizados")
    .update({
      estado: nuevoEstado,
      aprobado_en: accion === "aprobar" ? new Date().toISOString() : null,
    })
    .eq("fb_id", fb_id);

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

