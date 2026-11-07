import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export async function POST(req: Request) {
  const { source_id } = await req.json().catch(() => ({ source_id: "" }));
  if (!source_id) return NextResponse.json({ error: "Falta source_id" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });

  const { error } = await db.from("sources").update({ stop_requested: true }).eq("id", source_id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // Si el worker nunca llegó a tomarlo (sigue en cola), se cancela directo.
  await db.from("sources").update({ status: "stopped" }).eq("id", source_id).eq("status", "queued");
  await db.from("jobs").update({ status: "done" }).eq("source_id", source_id).eq("status", "queued");
  return NextResponse.json({ ok: true });
}
