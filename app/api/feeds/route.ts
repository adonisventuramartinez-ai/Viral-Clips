import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Fuentes de clips automáticos: el worker las revisa y crea solo los clips de los videos nuevos que van fuertes.
const TYPES = ["auto", "reality", "podcast", "entrevista", "juego", "gta", "gta6", "gta_rp", "directo"];
const num = (v: unknown, d: number, lo: number, hi: number) => { const n = Number(v); return Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.round(n))) : d; };
const msg = (m: string) => (/discover_|discovered_/i.test(m) ? "Falta ejecutar 0011_auto_clips.sql en Supabase" : m);

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, items: [], found: [] });
  const { data, error } = await db.from("discover_feeds").select("*").order("created_at", { ascending: false }).limit(30);
  if (error) return NextResponse.json({ error: msg(error.message), items: [], found: [] }, { status: 500 });
  const { data: found } = await db.from("discovered_videos").select("id,title,url,views,status,reason,created_at,feed_id").order("created_at", { ascending: false }).limit(40);
  const { data: ws } = await db.from("worker_status").select("info").eq("id", 1).maybeSingle();
  return NextResponse.json({ items: data ?? [], found: found ?? [], discover: (ws?.info as { discover?: boolean } | null)?.discover ?? null });
}

export async function POST(req: Request) {
  const b = await req.json().catch(() => ({}));
  const target = typeof b.target === "string" ? b.target.trim().slice(0, 200) : "";
  const kind = b.kind === "search" ? "search" : "channel";
  if (kind === "channel" && !/^https?:\/\/\S+$/i.test(target)) return NextResponse.json({ error: "El link del canal no es válido (debe empezar con https://)" }, { status: 400 });
  if (kind === "search" && target.length < 3) return NextResponse.json({ error: "Escribe qué buscar (mínimo 3 letras)" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });
  const { count } = await db.from("discover_feeds").select("id", { count: "exact", head: true });
  if ((count ?? 0) >= 15) return NextResponse.json({ error: "Máximo 15 fuentes" }, { status: 400 });
  const row = {
    name: typeof b.name === "string" && b.name.trim() ? b.name.trim().slice(0, 60) : null, kind, target,
    content_type: TYPES.includes(b.content_type) ? b.content_type : "auto",
    game: typeof b.game === "string" && b.game.trim() ? b.game.trim().slice(0, 60) : null,
    clips: num(b.clips, 4, 1, 15), min_minutes: num(b.min_minutes, 3, 1, 600), max_minutes: num(b.max_minutes, 120, 2, 600),
    max_age_hours: num(b.max_age_hours, 48, 1, 720), min_views: num(b.min_views, 0, 0, 100000000),
    clipper: typeof b.clipper === "string" && b.clipper.trim() ? b.clipper.trim().slice(0, 40) : null,
  };
  const { error } = await db.from("discover_feeds").insert(row);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}

/** active: true/false para pausar o reanudar · check_now: true para que el worker la revise en su próxima vuelta. */
export async function PATCH(req: Request) {
  const b = await req.json().catch(() => ({}));
  if (typeof b.id !== "string") return NextResponse.json({ error: "Falta id" }, { status: 400 });
  const upd: Record<string, unknown> = {};
  if (typeof b.active === "boolean") upd.active = b.active;
  if (b.check_now === true) upd.last_checked = null;
  if (!Object.keys(upd).length) return NextResponse.json({ error: "Nada que cambiar" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });
  const { error } = await db.from("discover_feeds").update(upd).eq("id", b.id);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function DELETE(req: Request) {
  const b = await req.json().catch(() => ({}));
  if (typeof b.id !== "string") return NextResponse.json({ error: "Falta id" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });
  const { error } = await db.from("discover_feeds").delete().eq("id", b.id);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}
