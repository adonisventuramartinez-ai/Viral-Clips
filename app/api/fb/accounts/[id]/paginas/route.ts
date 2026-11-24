import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { desencriptar } from "@/lib/crypto";
import { GRAPH_BASE } from "@/lib/graph";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();

  try {
    const { data: cuenta, error } = await supabaseAdmin
      .from("cuentas_fb")
      .select("token_encriptado")
      .eq("id", idParam)
      .eq("propietario_fb_id", sesion.sub)
      .single();

    if (error || !cuenta) {
      return NextResponse.json({ error: "Cuenta no encontrada" }, { status: 404 });
    }

    const token = desencriptar(cuenta.token_encriptado);
    const res = await fetch(
      `${GRAPH_BASE}/me/accounts?access_token=${encodeURIComponent(token)}&fields=id,name,category&limit=100`
    );
    const data = await res.json();

    if (data.error) {
      return NextResponse.json(
        { error: "El token de esta cuenta expiró o es inválido: " + data.error.message },
        { status: 400 }
      );
    }

    // Solo id/name/category: los tokens de página nunca salen del servidor.
    const paginas = (data.data || []).map((p: any) => ({ id: p.id, name: p.name, category: p.category }));
    return NextResponse.json({ paginas });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Error al obtener páginas" }, { status: 500 });
  }
}
