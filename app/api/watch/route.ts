import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Canales automáticos: el worker los vigila y graba solo cuando entran en vivo.
const COLS = "id,name,url,active,content_type,game,layout,clip_seconds,quality,review_minutes,max_new,progress_bar,last_checked,last_status";
const TYPES = ["auto", "podcast", "entrevista", "juego", "directo"];
const LAYOUTS = ["crop", "split", "split_eq", "split_game", "blur", "duo"];
const num = (v: unknown, d: number, lo: number, hi: number) => { const n = Number(v); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.round(n))) : d; };
const msg = (m: string) => (/watch_channels/i.test(m) ? "Falta ejecutar 0006_envivo.sql en Supabase" : m);

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, items: [] });
  const { data, error } = await db.from("watch_channels").select(COLS).order("created_at", { ascending: false }).limit(50);
  if (error) return NextResponse.json({ error: msg(error.message), items: [] }, { status: 500 });
  return NextResponse.json({ items: data ?? [] });
}

export async function POST(req: Request) {
  const b = await req.json().catch(() => ({}));
  const url = typeof b.url === "string" ? b.url.trim() : "";
  if (!/^https?:\/\/\S+$/i.test(url) || url.length > 500) return NextResponse.json({ error: "El link del canal no es válido (debe empezar con https://)" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });
  const { count } = await db.from("watch_channels").select("id", { count: "exact", head: true });
  if ((count ?? 0) >= 20) return NextResponse.json({ error: "Máximo 20 canales" }, { status: 400 });
  const row = {
    name: typeof b.name === "string" && b.name.trim() ? b.name.trim().slice(0, 60) : null,
    url,
    content_type: TYPES.includes(b.content_type) ? b.content_type : "auto",
    game: typeof b.game === "string" && b.game.trim() ? b.game.trim().slice(0, 60) : null,
    layout: LAYOUTS.includes(b.layout) ? b.layout : "crop",
    clip_seconds: num(b.clip_seconds, 45, 15, 120),
    quality: ["720p", "1080p", "1440p", "2160p"].includes(b.quality) ? b.quality : "720p",
    review_minutes: num(b.review_minutes, 2, 1, 10),
    max_new: num(b.max_new, 3, 1, 10),
    progress_bar: b.progress_bar === true,
    clipper: typeof b.clipper === "string" && b.clipper.trim() ? b.clipper.trim().slice(0, 40) : null,
  };
  const { error } = await db.from("watch_channels").insert(row);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function PATCH(req: Request) {
  const b = await req.json().catch(() => ({}));
  if (typeof b.id !== "string" || typeof b.active !== "boolean") return NextResponse.json({ error: "Datos incompletos" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });
  // al reactivar se olvida el último directo para que, si sigue en vivo, se pueda grabar otra vez
  const { error } = await db.from("watch_channels").update(b.active ? { active: true, last_video_id: null } : { active: false }).eq("id", b.id);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  const b = await req.json().catch(() => ({}));
  if (typeof b.id !== "string") return NextResponse.json({ error: "Falta id" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });
  const { error } = await db.from("watch_channels").delete().eq("id", b.id);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}
