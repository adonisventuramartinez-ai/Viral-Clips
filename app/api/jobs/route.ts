import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

// Crea una fuente + un trabajo en cola. El worker (Parte 2) lo toma desde la tabla `jobs`.
export async function POST(req: Request) {
  const body = await req.json();
  const { kind = "vod_url", url, range_from, range_to, clip_seconds = 45, clips = 15, quality = "1080p" } = body;

  if (kind !== "live" && !url) return NextResponse.json({ error: "Falta el link del video" }, { status: 400 });
  if (kind === "live" && !url) return NextResponse.json({ error: "Falta el link del directo" }, { status: 400 });

  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true, message: "Modo demo: conecta Supabase para encolar de verdad." });

  const { data: source, error } = await db
    .from("sources")
    .insert({ kind, url, range_from: range_from || null, range_to: range_to || null, status: "queued" })
    .select("id")
    .single();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const { error: jobErr } = await db.from("jobs").insert({
    source_id: source.id,
    type: kind === "live" ? "record" : "download",
    payload: { clip_seconds, clips, quality },
  });
  if (jobErr) return NextResponse.json({ error: jobErr.message }, { status: 500 });

  return NextResponse.json({ ok: true, source_id: source.id });
}
