import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

export const dynamic = "force-dynamic";
const MAX_PLANTILLAS = 50;

export async function GET(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  const { data, error } = await supabaseAdmin
    .from("plantillas")
    .select("id, nombre, titulo, mensaje")
    .eq("propietario_fb_id", sesion.sub)
    .order("nombre", { ascending: true });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ plantillas: data || [] });
}

export async function POST(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  try {
    const { nombre, titulo, mensaje } = await req.json();
    if (!nombre || typeof nombre !== "string" || nombre.length > 80) {
      return NextResponse.json({ error: "Nombre de plantilla inválido (máx. 80 caracteres)" }, { status: 400 });
    }
    if ((titulo && String(titulo).length > 255) || (mensaje && String(mensaje).length > 10000)) {
      return NextResponse.json({ error: "Título o mensaje demasiado largo" }, { status: 400 });
    }
    const { count } = await supabaseAdmin
      .from("plantillas")
      .select("id", { count: "exact", head: true })
      .eq("propietario_fb_id", sesion.sub);
    if ((count ?? 0) >= MAX_PLANTILLAS) {
      return NextResponse.json({ error: `Máximo ${MAX_PLANTILLAS} plantillas` }, { status: 400 });
    }
    const { data, error } = await supabaseAdmin
      .from("plantillas")
      .insert({ propietario_fb_id: sesion.sub, nombre: nombre.trim(), titulo: titulo || null, mensaje: mensaje || null })
      .select("id, nombre, titulo, mensaje")
      .single();
    if (error) throw error;
    return NextResponse.json({ plantilla: data });
  } catch (e: any) {
    return NextResponse.json({ error: e.message || "Error al guardar la plantilla" }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  const id = Number(req.nextUrl.searchParams.get("id"));
  if (!Number.isInteger(id)) return NextResponse.json({ error: "id inválido" }, { status: 400 });
  const { error } = await supabaseAdmin.from("plantillas").delete().eq("id", id).eq("propietario_fb_id", sesion.sub);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

