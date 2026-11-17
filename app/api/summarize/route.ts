import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { insertJob } from "@/lib/jobs";

export const dynamic = "force-dynamic";

/** Crea un resumen narrado (1 clip de 60-90 s) de un video largo. */
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const url = typeof body.url === "string" ? body.url.trim() : "";
  if (!url || !/^https?:\/\/\S+$/i.test(url) || url.length > 500) {
    return NextResponse.json({ error: "Falta un link válido (https://...)" }, { status: 400 });
  }
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true, message: "Modo demo: conecta Supabase para encolar de verdad." });

  const row = { kind: "vod_url", url, status: "queued", layout: "crop", custom_crop: null, clipper: null };
  const options = { content_type: "auto", game: null, progress_bar: true, brand_template: null, bleep: "auto", loudnorm: "auto", zoom: "auto", slowmo: "auto", tighten: "auto" };
  let ins = await db.from("sources").insert({ ...row, options }).select("id").single();
  if (ins.error && /options/i.test(ins.error.message)) ins = await db.from("sources").insert(row).select("id").single();
  const { data: source, error } = ins;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const payload = { clip_seconds: 90, clips: 1, quality: "1080p", content_type: "auto", game: null, progress_bar: true, brand_template: null, bleep: "auto", loudnorm: "auto", zoom: "auto", slowmo: "auto", tighten: "auto", layout: "crop" };
  const { error: jobErr } = await insertJob(db, { source_id: source.id, payload }, "download");
  if (jobErr) return NextResponse.json({ error: jobErr.message }, { status: 500 });

  return NextResponse.json({ ok: true, source_id: source.id });
}