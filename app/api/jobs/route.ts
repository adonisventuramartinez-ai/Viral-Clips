import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

const ACTIVE = ["queued", "downloading", "recording", "transcribing", "analyzing", "clipping"];

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  
  const { 
    kind = "vod_url", 
    url, 
    range_from, 
    range_to, 
    clip_seconds = 45, 
    clips = 15, 
    quality = "1080p", 
    review_minutes = 2,
    layout = "crop",
    custom_crop = null, // Recibe el encuadre
    clipper = null // Nombre público de quien crea el clip (ranking Clipeadores)
  } = body;

  if (!url) return NextResponse.json({ error: kind === "live" ? "Falta el link del directo" : "Falta el link del video" }, { status: 400 });
  if (typeof url !== "string" || !/^https?:\/\/\S+$/i.test(url.trim()) || url.length > 500) return NextResponse.json({ error: "El link no es válido (debe empezar con https://)" }, { status: 400 });
  if (!["vod_url", "live"].includes(kind)) return NextResponse.json({ error: "Tipo de trabajo no válido" }, { status: 400 });

  const num = (v: unknown, d: number, lo: number, hi: number) => { const n = Number(v); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.round(n))) : d; };
  const safe = {
    clip_seconds: num(clip_seconds, 45, 15, 120),
    clips: num(clips, 5, 1, 50),
    quality: ["720p", "1080p", "1440p", "2160p"].includes(quality) ? quality : "1080p",
    review_minutes: num(review_minutes, 2, 1, 10),
  };
  const safeLayout = ["crop", "split", "split_eq", "split_game", "blur", "duo"].includes(layout) ? layout : "crop";

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
    .insert({ 
      kind, 
      url: url.trim(), 
      range_from: range_from || null, 
      range_to: range_to || null, 
      status: "queued",
      layout: safeLayout,
      custom_crop: custom_crop, // Guarda el encuadre
      clipper: typeof clipper === "string" && clipper.trim() ? clipper.trim().slice(0, 40) : null
    })
    .select("id")
    .single();
    
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const { error: jobErr } = await db.from("jobs").insert({
    source_id: source.id,
    type: kind === "live" ? "record" : "download",
    payload: safe,
  });
  if (jobErr) return NextResponse.json({ error: jobErr.message }, { status: 500 });

  return NextResponse.json({ ok: true, source_id: source.id });
}
