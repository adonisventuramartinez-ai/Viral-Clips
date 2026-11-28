import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { removeClipFiles, signClipPaths } from "@/lib/storage";
import { nextSlot } from "@/lib/slots";

export const dynamic = "force-dynamic";

/** Carga un clip para el editor: datos + URLs firmadas (Tigris o Supabase, con respaldo). */
export async function GET(_req: Request, { params }: { params: { id: string } }) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const { data, error } = await db.from("clips").select("*").eq("id", params.id).maybeSingle();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!data) return NextResponse.json({ error: "Clip no encontrado" }, { status: 404 });

  const { data: src } = await db.from("sources").select("kind,title,url").eq("id", data.source_id).maybeSingle();
  const paths = [data.storage_path, data.thumb_path, data.thumb_b_path].filter(Boolean) as string[];
  const [view, download] = await Promise.all([
    paths.length ? signClipPaths(paths, 3600, false, db) : Promise.resolve([]),
    data.storage_path ? signClipPaths([data.storage_path], 3600, true, db) : Promise.resolve([]),
  ]);
  const byPath = new Map(view.map((x) => [x.path, x.signedUrl]));
  return NextResponse.json({
    clip: {
      ...data,
      sourceKind: src?.kind ?? null,
      sourceTitle: src?.title ?? null,
      videoUrl: data.storage_path ? byPath.get(data.storage_path) ?? null : null,
      downloadUrl: download[0]?.signedUrl ?? null,
      thumbUrl: data.thumb_path ? byPath.get(data.thumb_path) ?? null : null,
      thumbBUrl: data.thumb_b_path ? byPath.get(data.thumb_b_path) ?? null : null,
    },
  });
}

export async function DELETE(_req: Request, { params }: { params: { id: string } }) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });

  const { data: clip, error: fetchError } = await db.from("clips").select("storage_path").eq("id", params.id).single();
  if (fetchError || !clip) return NextResponse.json({ error: "Clip no encontrado" }, { status: 404 });

  if (clip.storage_path) {
    const { error } = await removeClipFiles([clip.storage_path], db);
    if (error) console.error("Error borrando archivo:", error);
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
    // horas aprendidas de Facebook (o de todas las redes) en Mi página; sin datos suficientes se usan POST_SLOTS
    const { data: bh } = await db.from("best_hours").select("network,slot").eq("chosen", true).in("network", ["facebook", "all"]);
    const mine = (bh ?? []).filter((h) => h.network === "facebook");
    const learned = (mine.length ? mine : bh ?? []).map((h) => String(h.slot));
    const at = nextSlot((rows ?? []).map((r) => String(r.scheduled_at)), new Date(), learned);
    if (!at) return NextResponse.json({ error: "No hay horas libres configuradas (POST_SLOTS)" }, { status: 409 });
    upd.scheduled_at = at.toISOString(); upd.publish_status = "scheduled"; upd.publish_error = null;
    if (!upd.viral_status) upd.viral_status = "approved";
  }
  if (!Object.keys(upd).length) return NextResponse.json({ error: "Nada que cambiar" }, { status: 400 });
  const { error } = await db.from("clips").update(upd).eq("id", params.id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
