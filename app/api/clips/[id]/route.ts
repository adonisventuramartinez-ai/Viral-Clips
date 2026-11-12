import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });

  const { data: clip, error: fetchError } = await db.from("clips").select("storage_path").eq("id", params.id).single();
  if (fetchError || !clip) return NextResponse.json({ error: "Clip no encontrado" }, { status: 404 });

  if (clip.storage_path) {
    const { error } = await db.storage.from("clips").remove([clip.storage_path]);
    if (error) console.error("Error borrando archivo:", error.message);
  }
  const { error: deleteError } = await db.from("clips").delete().eq("id", params.id);
  if (deleteError) return NextResponse.json({ error: deleteError.message }, { status: 500 });
  return NextResponse.json({ success: true });
}

/** Cambia si el clip aparece en el feed/Top de la comunidad, o su título. */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const upd: Record<string, unknown> = {};
  if (typeof b.is_public === "boolean") upd.is_public = b.is_public;
  if (typeof b.title === "string" && b.title.trim()) upd.title = b.title.trim().slice(0, 80);
  if (!Object.keys(upd).length) return NextResponse.json({ error: "Nada que cambiar" }, { status: 400 });
  const { error } = await db.from("clips").update(upd).eq("id", params.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
