import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { adminDe, noAutorizado } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  if (!(await adminDe(req))) return noAutorizado();

  const { data, error } = await supabaseAdmin
    .from("usuarios_autorizados")
    .select("*")
    .order("solicitado_en", { ascending: false });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ solicitudes: data });
}

