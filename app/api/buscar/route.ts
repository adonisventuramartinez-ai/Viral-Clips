import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { insertJob } from "@/lib/jobs";

export const dynamic = "force-dynamic";

// Buscador de clips virales: la web solo crea la búsqueda y lee resultados; quien rastrea es el worker.
const msg = (m: string) =>
  /clip_search|jobs|syntax error|relation .* does not exist|column .* does not exist/i.test(m)
    ? "Falta ejecutar supabase/migrations/0019_buscador.sql en Supabase. " + m
    : m;

const num = (v: unknown, d: number, lo: number, hi: number) => {
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, Math.round(n))) : d;
};

const arr = (v: unknown) => {
  const parts = Array.isArray(v)
    ? v
    : String(v ?? "")
        .split(/[\n,;]+/)
        .map((x) => x.trim());
  return Array.from(new Set(parts.map((x) => String(x).trim()).filter(Boolean))).slice(0, 40);
};

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, searches: [], results: [] });
  const { data: searches, error } = await db
    .from("clip_searches")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(20);
  if (error) return NextResponse.json({ error: msg(error.message), searches: [], results: [] }, { status: 500 });
  const ids = (searches ?? []).map((s: { id: string }) => s.id);
  const { data: results } = ids.length
    ? await db
        .from("clip_search_results")
        .select("*")
        .in_("search_id", ids)
        .order("score", { ascending: false })
        .limit(300)
    : { data: [] };
  return NextResponse.json({ searches: searches ?? [], results: results ?? [] });
}

export async function POST(req: Request) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Faltan las llaves de Supabase en Vercel" }, { status: 500 });
  let b: Record<string, unknown> = {};
  try {
    b = await req.json();
  } catch {
    return NextResponse.json({ error: "JSON inválido" }, { status: 400 });
  }
  const accounts = arr(b.accounts);
  const links = arr(b.links);
  const query = String(b.query ?? "").trim().slice(0, 120);
  if (!accounts.length && !links.length && !query) {
    return NextResponse.json({ error: "Escribe un tema o pega perfiles/links de TikTok o Reels" }, { status: 400 });
  }
  const row = {
    user_id: null,
    query: query || null,
    networks: arr(b.networks).length ? arr(b.networks) : ["tiktok", "instagram"],
    accounts,
    links,
    min_views: num(b.min_views, 10000, 0, 100000000),
    max_age_hours: num(b.max_age_hours, 72, 1, 720),
    max_results: num(b.max_results, 10, 1, 50),
    auto_queue: num(b.auto_queue, 5, 0, 30),
    content_type: String(b.content_type ?? "auto").slice(0, 40),
    publish_fb: b.publish_fb !== false,
    status: "queued",
  };
  const { data: search, error } = await db.from("clip_searches").insert(row).select("id").single();
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  const { error: jobErr } = await insertJob(db, { source_id: null, payload: { search_id: search.id } }, "search");
  if (jobErr) return NextResponse.json({ error: msg(jobErr.message) }, { status: 500 });
  return NextResponse.json({ ok: true, id: search.id });
}

export async function PATCH(req: Request) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Faltan las llaves de Supabase en Vercel" }, { status: 500 });
  let b: Record<string, unknown> = {};
  try {
    b = await req.json();
  } catch {
    return NextResponse.json({ error: "JSON inválido" }, { status: 400 });
  }
  const id = String(b.id ?? "");
  const ids = arr(b.ids);
  if (!id || !ids.length) return NextResponse.json({ error: "Faltan resultados para encolar" }, { status: 400 });
  const { error } = await insertJob(db, { source_id: null, payload: { search_id: id, mode: "queue", ids } }, "search");
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}
