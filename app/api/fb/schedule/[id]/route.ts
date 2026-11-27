import { NextRequest, NextResponse } from "next/server";
import { supabaseAdmin } from "@/lib/db";
import { noAutorizado, sesionDe } from "@/lib/fbAuth";

function idValido(id: string): number | null {
  const n = Number(id);
  return Number.isInteger(n) && n > 0 ? n : null;
}

// DELETE: cancela una publicación pendiente o con error
export async function DELETE(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  const id = idValido(idParam);
  if (!id) return NextResponse.json({ error: "ID inválido" }, { status: 400 });

  const { data, error } = await supabaseAdmin
    .from("posts_programados")
    .update({ estado: "cancelado" })
    .eq("id", id)
    .eq("propietario_fb_id", sesion.sub)
    .in("estado", ["pendiente", "error"])
    .select("id");

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data?.length) return NextResponse.json({ error: "No se pudo cancelar (¿ya se está publicando?)" }, { status: 409 });
  return NextResponse.json({ ok: true });
}

// PATCH:
//   { accion: "reintentar" }          → un post en error vuelve a la cola (las páginas que ya salieron NO se repiten)
//   { fecha_programada: ISO }         → reprograma un post pendiente
export async function PATCH(req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id: idParam } = await params;
  const sesion = await sesionDe(req);
  if (!sesion) return noAutorizado();
  const id = idValido(idParam);
  if (!id) return NextResponse.json({ error: "ID inválido" }, { status: 400 });

  const body = await req.json().catch(() => ({}));

  if (body.accion === "reintentar") {
    // Se conserva la fecha de calendario original para que una serie recurrente no se desplace
    const { data: previo } = await supabaseAdmin
      .from("posts_programados")
      .select("fecha_programada, fecha_original")
      .eq("id", id)
      .eq("propietario_fb_id", sesion.sub)
      .maybeSingle();
    const cambios: Record<string, unknown> = {
      estado: "pendiente",
      intentos: 0,
      fecha_programada: new Date().toISOString(),
      ultimo_error: null,
    };
    if (previo && !previo.fecha_original) cambios.fecha_original = previo.fecha_programada;

    const { data, error } = await supabaseAdmin
      .from("posts_programados")
      .update(cambios)
      .eq("id", id)
      .eq("propietario_fb_id", sesion.sub)
      .eq("estado", "error")
      .select("id");
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    if (!data?.length) return NextResponse.json({ error: "Solo se pueden reintentar posts con error" }, { status: 409 });
    return NextResponse.json({ ok: true });
  }

  if (body.fecha_programada) {
    const fecha = new Date(body.fecha_programada);
    if (isNaN(fecha.getTime()) || fecha.getTime() <= Date.now()) {
      return NextResponse.json({ error: "La fecha debe ser válida y en el futuro" }, { status: 400 });
    }
    const reprogramar = (extra: Record<string, unknown>) =>
      supabaseAdmin
        .from("posts_programados")
        .update({ fecha_programada: fecha.toISOString(), ...extra })
        .eq("id", id)
        .eq("propietario_fb_id", sesion.sub)
        .eq("estado", "pendiente")
        .select("id");
    // fecha_original: null = "la nueva fecha manda" (columna de la migración 005; si falta, se reintenta sin ella)
    let { data, error } = await reprogramar({ fecha_original: null });
    if (error) ({ data, error } = await reprogramar({}));
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    if (!data?.length) return NextResponse.json({ error: "Solo se pueden reprogramar posts pendientes" }, { status: 409 });
    return NextResponse.json({ ok: true });
  }

  return NextResponse.json({ error: "Nada que actualizar" }, { status: 400 });
}
