import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const ACTIVE = ["queued", "downloading", "recording", "transcribing", "analyzing", "clipping"];

// Crea una fuente + un trabajo en cola. El worker lo toma desde la tabla `jobs`.
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const { kind = "vod_url", url, range_from, range_to, clip_seconds = 45, clips = 15, quality = "1080p", review_minutes = 2 } = body;

  if (!url) return NextResponse.json({ error: kind === "live" ? "Falta el link del directo" : "Falta el link del video" }, { status: 400 });

  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true, message: "Modo demo: conecta Supabase para encolar de verdad." });

  if (kind === "live") {
    const { data: running } = await db.from("sources").select("id").eq("kind", "live").in("status", ACTIVE).limit(1);
    if (running && running.length) {
      return NextResponse.json({ error: "Ya hay un directo grabando. Páralo antes de empezar otro." }, { status: 409 });
    }
  }

  const { data: source, error } = await db
    .from("sources")
    .insert({ kind, url, range_from: range_from || null, range_to: range_to || null, status: "queued" })
    .select("id")
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const { error: jobErr } = await db.from("jobs").insert({
    source_id: source.id,
    type: kind === "live" ? "record" : "download",
    payload: { clip_seconds, clips, quality, review_minutes },
  });
  if (jobErr) return NextResponse.json({ error: jobErr.message }, { status: 500 });

  return NextResponse.json({ ok: true, source_id: source.id });
}
