import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Un solo endpoint para la parte "comunidad". GET /api/hub/<recurso>
//  stats · feed · top · clippers · suggestions · donors · programs · socials · mystats
const FEED_COLS = "id,title,start_sec,end_sec,viral_score,storage_path,clipper,created_at,source_id,sources(title)";

async function signed(db: any, rows: any[]) {
  const paths = rows.map((r) => r.storage_path).filter(Boolean) as string[];
  const map = new Map<string, string>();
  if (paths.length) {
    const { data } = await db.storage.from("clips").createSignedUrls(paths, 3600);
    (data ?? []).forEach((x: any) => x.path && x.signedUrl && map.set(x.path, x.signedUrl));
  }
  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    seconds: Math.round(Number(r.end_sec) - Number(r.start_sec)),
    score: r.viral_score,
    clipper: r.clipper ?? "anónimo",
    source: r.sources?.title ?? null,
    createdAt: r.created_at,
    videoUrl: r.storage_path ? map.get(r.storage_path) ?? null : null,
  }));
}

export async function GET(req: Request, { params }: { params: { resource: string } }) {
  const db = serverClient() as any;
  const url = new URL(req.url);
  const r = params.resource;
  if (!db) return NextResponse.json({ demo: true, items: [], stats: { clips: 0, creators: 0, users: 0 } });

  try {
    if (r === "stats") {
      const { data, error } = await db.rpc("site_stats");
      if (error) throw error;
      return NextResponse.json({ stats: data });
    }
    if (r === "feed" || r === "top") {
      const q = db.from("clips").select(FEED_COLS).eq("is_public", true).not("storage_path", "is", null);
      const ordered = r === "top"
        ? q.order("viral_score", { ascending: false }).order("created_at", { ascending: false })
        : q.order("created_at", { ascending: false });
      const { data, error } = await ordered.limit(Number(url.searchParams.get("limit")) || (r === "top" ? 30 : 12));
      if (error) throw error;
      return NextResponse.json({ items: await signed(db, data ?? []) });
    }
    if (r === "clippers") {
      const { data, error } = await db.rpc("top_clippers", { lim: 30 });
      if (error) throw error;
      return NextResponse.json({ items: data ?? [] });
    }
    if (r === "mystats") {
      const who = url.searchParams.get("clipper");
      let q = db.from("clips").select("viral_score,created_at,size_bytes");
      if (who) q = q.eq("clipper", who);
      const { data, error } = await q.order("created_at", { ascending: false }).limit(2000);
      if (error) throw error;
      const rows: any[] = data ?? [];
      const days: Record<string, number> = {};
      for (let i = 6; i >= 0; i--) days[new Date(Date.now() - i * 864e5).toISOString().slice(0, 10)] = 0;
      rows.forEach((c) => { const d = String(c.created_at).slice(0, 10); if (d in days) days[d]++; });
      return NextResponse.json({
        total: rows.length,
        avg: rows.length ? Math.round(rows.reduce((a, c) => a + c.viral_score, 0) / rows.length) : 0,
        best: rows.reduce((a, c) => Math.max(a, c.viral_score), 0),
        mb: Math.round(rows.reduce((a, c) => a + Number(c.size_bytes ?? 0), 0) / 1048576),
        days,
      });
    }
    const tables: Record<string, [string, string]> = {
      suggestions: ["suggestions", "id,author,body,votes,created_at"],
      donors: ["donors", "id,name,amount,message,created_at"],
      programs: ["programs", "id,name,channel_url,schedule"],
      socials: ["social_accounts", "id,clipper,platform,handle"],
    };
    const t = tables[r];
    if (!t) return NextResponse.json({ error: "Recurso desconocido" }, { status: 404 });
    let q = db.from(t[0]).select(t[1]);
    const who = url.searchParams.get("clipper");
    if (r === "socials" && who) q = q.eq("clipper", who);
    const order = r === "suggestions" ? "votes" : r === "donors" ? "amount" : "created_at";
    const { data, error } = await q.order(order, { ascending: false, nullsFirst: false }).limit(100);
    if (error) throw error;
    return NextResponse.json({ items: data ?? [] });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message ?? "Error" }, { status: 500 });
  }
}

const clean = (v: unknown, max = 300) => (typeof v === "string" ? v.trim().slice(0, max) : "");

export async function POST(req: Request, { params }: { params: { resource: string } }) {
  const db = serverClient() as any;
  if (!db) return NextResponse.json({ ok: true, demo: true });
  const b = await req.json().catch(() => ({}));
  const r = params.resource;
  let res: any;

  if (r === "suggestions") {
    if (b.vote && typeof b.id === "string") {
      const { data } = await db.from("suggestions").select("votes").eq("id", b.id).maybeSingle();
      res = await db.from("suggestions").update({ votes: (data?.votes ?? 0) + 1 }).eq("id", b.id);
    } else {
      if (clean(b.body, 500).length < 5) return NextResponse.json({ error: "Escribe al menos 5 caracteres" }, { status: 400 });
      res = await db.from("suggestions").insert({ author: clean(b.author, 40) || null, body: clean(b.body, 500) });
    }
  } else if (r === "socials") {
    if (!["tiktok", "instagram", "youtube"].includes(b.platform) || !clean(b.clipper, 40) || !clean(b.handle, 60)) return NextResponse.json({ error: "Datos incompletos" }, { status: 400 });
    res = await db.from("social_accounts").upsert({ clipper: clean(b.clipper, 40), platform: b.platform, handle: clean(b.handle, 60).replace(/^@/, "") }, { onConflict: "clipper,platform" });
  } else {
    return NextResponse.json({ error: "No permitido" }, { status: 405 });
  }
  if (res.error) return NextResponse.json({ error: res.error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
