import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { insertJob } from "@/lib/jobs";

export const dynamic = "force-dynamic";

/** Reintenta una fuente que falló: la pone otra vez en cola con las mismas opciones. Body: { id } */
export async function POST(req: Request) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const { id } = await req.json().catch(() => ({}));
  if (typeof id !== "string" || !id) return NextResponse.json({ error: "Falta el id" }, { status: 400 });

  const { data: src } = await db.from("sources").select("id,kind,status").eq("id", id).maybeSingle();
  if (!src) return NextResponse.json({ error: "Esa fuente ya no existe" }, { status: 404 });
  if (src.status !== "error") return NextResponse.json({ error: "Solo se pueden reintentar las que fallaron" }, { status: 409 });
  if (src.kind === "live") return NextResponse.json({ error: "Un directo que falló no se puede repetir: ya pasó. Empieza otro desde En vivo." }, { status: 400 });

  // mismas opciones que la vez anterior: se copian del último trabajo de esa fuente
  const { data: last } = await db.from("jobs").select("payload").eq("source_id", id).order("created_at", { ascending: false }).limit(1);
  const payload = last?.[0]?.payload ?? {};

  await db.from("jobs").update({ status: "done" }).eq("source_id", id).in("status", ["queued", "running", "error"]);   // cierra los viejos
  const { error } = await insertJob(db, { source_id: id, payload }, "download");
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  await db.from("sources").update({ status: "queued", error: null }).eq("id", id);
  return NextResponse.json({ ok: true });
}
