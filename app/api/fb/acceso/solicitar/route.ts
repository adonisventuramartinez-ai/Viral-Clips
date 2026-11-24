import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";

function generarCodigo(): string {
  return Math.floor(100000 + Math.random() * 900000).toString(); // 6 dígitos
}

export async function POST(req: NextRequest) {
  try {
    const { fb_id, nombre } = await req.json();
    if (!fb_id || !nombre) {
      return NextResponse.json({ error: "Faltan datos (fb_id, nombre)" }, { status: 400 });
    }

    // ¿Ya existe una solicitud de esta persona?
    const { data: existente } = await supabaseAdmin
      .from("usuarios_autorizados")
      .select("*")
      .eq("fb_id", fb_id)
      .maybeSingle();

    if (existente) {
      return NextResponse.json({
        estado: existente.estado,
        codigo_solicitud: existente.codigo_solicitud,
      });
    }

    const codigo = generarCodigo();
    const { error } = await supabaseAdmin.from("usuarios_autorizados").insert({
      fb_id,
      nombre,
      codigo_solicitud: codigo,
      estado: "pendiente",
    });

    if (error) throw error;

    return NextResponse.json({ estado: "pendiente", codigo_solicitud: codigo });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al registrar solicitud" }, { status: 500 });
  }
}

