import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";

export async function GET(req: NextRequest) {
  const fb_id = req.nextUrl.searchParams.get("fb_id");
  if (!fb_id) {
    return NextResponse.json({ error: "Falta fb_id" }, { status: 400 });
  }

  const { data, error } = await supabaseAdmin
    .from("usuarios_autorizados")
    .select("estado, codigo_solicitud")
    .eq("fb_id", fb_id)
    .maybeSingle();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data) return NextResponse.json({ estado: "no_encontrado" });

  return NextResponse.json(data);
}

