import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin, BUCKET } from "@/lib/db";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";
import { despacharWorker } from "@/lib/github";

export const dynamic = "force-dynamic";

function idValido(id: string): number | null {
  const n = Number(id);
  return Number.isInteger(n) && n > 0 ? n : null;
}

// DELETE: borra la importación. Si el video aún no se usó, también borra el archivo.
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  const id = idValido(idParam);
  if (!id) return NextResponse.json({ error: "ID inválido" }, { status: 400 });

  const { data: fila } = await supabaseAdmin
    .from("importaciones")
    .select("estado, archivo_url, miniatura_path")
    .eq("id", id)
    .eq("propietario_fb_id", sesion.sub)
    .maybeSingle();
  if (!fila) return NextResponse.json({ error: "No encontrada" }, { status: 404 });
  if (fila.estado === "procesando") return NextResponse.json({ error: "Se está procesando ahora mismo; espera un momento" }, { status: 409 });

  // Si ya está "usado", un post programado depende del video: no se toca el archivo.
  const borrar: string[] = [];
  if (fila.estado !== "usado" && fila.archivo_url) borrar.push(fila.archivo_url);
  if (fila.miniatura_path) borrar.push(fila.miniatura_path);
  if (borrar.length) await supabaseAdmin.storage.from(BUCKET).remove(borrar);

  const { error } = await supabaseAdmin.from("importaciones").delete().eq("id", id).eq("propietario_fb_id", sesion.sub);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

// PATCH { accion: "reintentar" } → un trabajo con error vuelve a la cola
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  const id = idValido(idParam);
  if (!id) return NextResponse.json({ error: "ID inválido" }, { status: 400 });

  const body = await req.json().catch(() => ({}));
  if (body.accion !== "reintentar") return NextResponse.json({ error: "Acción no válida" }, { status: 400 });

  const { data, error } = await supabaseAdmin
    .from("importaciones")
    .update({ estado: "pendiente", error: null, iniciado_en: null })
    .eq("id", id)
    .eq("propietario_fb_id", sesion.sub)
    .eq("estado", "error")
    .select("id");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data?.length) return NextResponse.json({ error: "Solo se pueden reintentar importaciones con error" }, { status: 409 });

  const despacho = await despacharWorker();
  return NextResponse.json({ ok: true, despacho });
}
