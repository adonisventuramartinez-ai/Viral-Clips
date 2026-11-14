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
    clipper = null, // Nombre público de quien crea el clip (ranking Clipeadores)
    content_type = "auto", // auto | reality | podcast | entrevista | juego | gta | gta6 | gta_rp | directo
    game = null, // nombre del juego (ayuda a la IA a entender las jugadas)
    progress_bar = false, // barra de progreso abajo del clip
    bleep = "auto", loudnorm = "auto", zoom = "auto", slowmo = "auto", // audio y efectos: "auto" | "1" | "0"
    max_new = 3 // en vivo: máximo de clips nuevos por revisión
  } = body;

  if (!url) return NextResponse.json({ error: kind === "live" ? "Falta el link del directo" : "Falta el link del video" }, { status: 400 });
  if (typeof url !== "string" || !/^https?:\/\/\S+$/i.test(url.trim()) || url.length > 500) return NextResponse.json({ error: "El link no es válido (debe empezar con https://)" }, { status: 400 });
  if (!["vod_url", "live"].includes(kind)) return NextResponse.json({ error: "Tipo de trabajo no válido" }, { status: 400 });

  const num = (v: unknown, d: number, lo: number, hi: number) => { const n = Number(v); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.round(n))) : d; };
  const safe = {
    clip_seconds: Number(clip_seconds) === 0 || clip_seconds === "auto" ? 0 : num(clip_seconds, 0, 15, 120), // 0 = automática: el worker usa el largo ideal del tipo
    clips: num(clips, 5, 1, 50),
    quality: ["720p", "1080p", "1440p", "2160p"].includes(quality) ? quality : "1080p",
    review_minutes: num(review_minutes, 2, 1, 10),
    ...(kind === "live" ? { max_new: num(max_new, 3, 1, 10) } : {}),
  };
  const safeType = ["auto", "reality", "podcast", "entrevista", "juego", "gta", "gta6", "gta_rp", "directo"].includes(content_type) ? content_type : "auto";
  const safeGame = typeof game === "string" && game.trim() ? game.trim().slice(0, 60) : null;
  const tri = (v: unknown) => (v === "1" || v === true ? "1" : v === "0" || v === false ? "0" : "auto");
  const options = { content_type: safeType, game: safeGame, progress_bar: progress_bar === true, bleep: tri(bleep), loudnorm: tri(loudnorm), zoom: tri(zoom), slowmo: tri(slowmo) };
  Object.assign(safe, options);
  const safeLayout = ["crop", "split", "split_eq", "split_game", "blur", "duo"].includes(layout) ? layout : "crop";

  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true, message: "Modo demo: conecta Supabase para encolar de verdad." });

  if (kind === "live") {
    const { data: running } = await db.from("sources").select("id").eq("kind", "live").in("status", ACTIVE).limit(1);
    if (running && running.length) {
      return NextResponse.json({ error: "Ya hay un directo grabando. Páralo antes de empezar otro." }, { status: 409 });
    }
  }

  const row = {
    kind,
    url: url.trim(),
    range_from: range_from || null,
    range_to: range_to || null,
    status: "queued",
    layout: safeLayout,
    custom_crop: custom_crop, // Guarda el encuadre
    clipper: typeof clipper === "string" && clipper.trim() ? clipper.trim().slice(0, 40) : null,
  };
  // Si aún no corriste 0005_calidad.sql no existe la columna "options": se reintenta sin ella (las opciones igual viajan en el trabajo).
  let ins = await db.from("sources").insert({ ...row, options }).select("id").single();
  if (ins.error && /options/i.test(ins.error.message)) ins = await db.from("sources").insert(row).select("id").single();
  const { data: source, error } = ins;
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const { error: jobErr } = await db.from("jobs").insert({
    source_id: source.id,
    type: kind === "live" ? "record" : "download",
    payload: safe,
  });
  if (jobErr) return NextResponse.json({ error: jobErr.message }, { status: 500 });

  return NextResponse.json({ ok: true, source_id: source.id });
}
