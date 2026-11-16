import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { nextSlot } from "@/lib/slots";

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

/** Cambia si el clip aparece en el feed/Top de la comunidad, su título, o su hora de publicación programada. */
export async function PATCH(req: Request, { params }: { params: { id: string } }) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const upd: Record<string, unknown> = {};
  if (typeof b.is_public === "boolean") upd.is_public = b.is_public;
  if (typeof b.title === "string" && b.title.trim()) upd.title = b.title.trim().slice(0, 80);
  // Programar la publicación en Facebook: scheduled_at = fecha ISO (entre 1 minuto y 60 días) o null para cancelar
  if ("scheduled_at" in b) {
    const { data: cur } = await db.from("clips").select("publish_status").eq("id", params.id).maybeSingle();
    if (cur?.publish_status === "published") return NextResponse.json({ error: "Este clip ya se publicó" }, { status: 409 });
    if (b.scheduled_at === null) {
      upd.scheduled_at = null; upd.publish_status = null; upd.publish_error = null;
    } else {
      const t = Date.parse(String(b.scheduled_at));
      const now = Date.now();
      if (!Number.isFinite(t) || t < now + 60_000 || t > now + 60 * 86_400_000)
        return NextResponse.json({ error: "Elige una fecha entre dentro de 1 minuto y 60 días" }, { status: 400 });
      upd.scheduled_at = new Date(t).toISOString(); upd.publish_status = "scheduled"; upd.publish_error = null;
    }
  }
  // Área viral: aprobar o descartar a mano
  if (b.viral_status === "approved" || b.viral_status === "rejected") upd.viral_status = b.viral_status;
  // "Mejor hora": elige la próxima hora buena libre (ver lib/slots.ts) y programa el clip
  if (b.auto_slot === true) {
    const { data: cur } = await db.from("clips").select("publish_status").eq("id", params.id).maybeSingle();
    if (cur?.publish_status === "published") return NextResponse.json({ error: "Este clip ya se publicó" }, { status: 409 });
    const { data: rows } = await db.from("clips").select("scheduled_at").eq("publish_status", "scheduled");
    const at = nextSlot((rows ?? []).map((r) => String(r.scheduled_at)));
    if (!at) return NextResponse.json({ error: "No hay horas libres configuradas (POST_SLOTS)" }, { status: 409 });
    upd.scheduled_at = at.toISOString(); upd.publish_status = "scheduled"; upd.publish_error = null;
    if (!upd.viral_status) upd.viral_status = "approved";
  }
  if (!Object.keys(upd).length) return NextResponse.json({ error: "Nada que cambiar" }, { status: 400 });
  const { error } = await db.from("clips").update(upd).eq("id", params.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
