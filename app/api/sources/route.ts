import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Estados que se pueden limpiar (todo menos "done").
const CLEARABLE = ["queued", "downloading", "recording", "transcribing", "analyzing", "clipping", "error", "stopped"];
const LIVE_RUNNING = ["downloading", "recording", "transcribing", "analyzing", "clipping"];
const MAX = 100;

/**
 * Limpia la Biblioteca de trabajos pegados.
 * Body: {} -> limpia todo lo en cola / con error / detenido / atascado
 *       { id } -> quita solo esa fuente
 * Reglas de seguridad:
 *  - Una fuente que ya tiene clips NO se borra (sus clips se perderían): se marca como "done".
 *  - Un directo que está grabando de verdad NO se borra: se le pide parar.
 */
export async function DELETE(req: Request) {
  const body = await req.json().catch(() => ({}));
  const id = typeof body?.id === "string" ? body.id : "";

  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true, removed: 0, kept: 0, stopping: 0 });

  let q = db.from("sources").select("id,kind,status").in("status", CLEARABLE);
  if (id) q = q.eq("id", id);
  const { data, error } = await q.order("created_at", { ascending: true }).limit(MAX);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const rows = data ?? [];
  if (!rows.length) return NextResponse.json({ ok: true, found: 0, removed: 0, kept: 0, stopping: 0, more: false });

  // 1) Directos grabando: pedir paro en vez de borrar
  const stopIds = rows.filter((r) => r.kind === "live" && LIVE_RUNNING.includes(r.status)).map((r) => r.id as string);
  if (stopIds.length) {
    const { error: e } = await db.from("sources").update({ stop_requested: true }).in("id", stopIds);
    if (e) return NextResponse.json({ error: e.message }, { status: 500 });
  }

  // 2) De los demás, separar los que ya tienen clips
  const rest = rows.filter((r) => !stopIds.includes(r.id as string)).map((r) => r.id as string);
  let keepIds: string[] = [];
  if (rest.length) {
    const { data: withClips, error: e } = await db.from("clips").select("source_id").in("source_id", rest).limit(5000);
    if (e) return NextResponse.json({ error: e.message }, { status: 500 });
    keepIds = Array.from(new Set((withClips ?? []).map((c) => c.source_id as string)));
  }
  const deleteIds = rest.filter((x) => !keepIds.includes(x));

  if (keepIds.length) {
    const { error: e } = await db.from("sources").update({ status: "done", error: null }).in("id", keepIds);
    if (e) return NextResponse.json({ error: e.message }, { status: 500 });
    await db.from("jobs").update({ status: "done" }).in("source_id", keepIds).in("status", ["queued", "running"]);
  }

  // 3) Borrar el resto (jobs, transcripción y descartados se van solos por cascade)
  if (deleteIds.length) {
    const { error: e } = await db.from("sources").delete().in("id", deleteIds);
    if (e) return NextResponse.json({ error: e.message }, { status: 500 });
  }

  return NextResponse.json({
    ok: true,
    found: rows.length,
    removed: deleteIds.length,
    kept: keepIds.length,
    stopping: stopIds.length,
    more: !id && rows.length === MAX,
  });
}
