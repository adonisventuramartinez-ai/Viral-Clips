import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Mi página: números de lo que publicaste (los lee el worker, ver worker/insights.py), horas aprendidas y seguidores.
const NETS = ["facebook", "instagram", "youtube"] as const;
const msg = (m: string) => (/post_stats|best_hours|page_followers/i.test(m) ? "Falta correr 0012_mi_pagina.sql en Supabase" : m);

type Stat = { network: string; external_id: string; clip_id: string | null; published_at: string | null; views: number; likes: number; comments: number; shares: number; error: string | null; fetched_at: string };

export async function GET(req: Request) {
  const days = Math.min(90, Math.max(1, Number(new URL(req.url).searchParams.get("days")) || 30));
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, totals: null }, { status: 200 });
  const since = new Date(Date.now() - days * 86_400_000).toISOString();
  const { data: stats, error } = await db.from("post_stats").select("*").gte("published_at", since).order("published_at", { ascending: false }).limit(2000);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  const rows = (stats ?? []) as Stat[];

  const ids = Array.from(new Set(rows.map((r) => r.clip_id).filter(Boolean))) as string[];
  const titles = new Map<string, { title: string; viral_score: number }>();
  if (ids.length) {
    const { data: cl } = await db.from("clips").select("id,title,viral_score").in("id", ids.slice(0, 500));
    (cl ?? []).forEach((c: any) => titles.set(c.id, { title: c.title, viral_score: c.viral_score }));
  }

  const sum = (xs: Stat[], k: "views" | "likes" | "comments" | "shares") => xs.reduce((a, r) => a + Number(r[k] ?? 0), 0);
  const pack = (xs: Stat[]) => ({ posts: xs.length, views: sum(xs, "views"), likes: sum(xs, "likes"), comments: sum(xs, "comments"), shares: sum(xs, "shares"), avg: xs.length ? Math.round(sum(xs, "views") / xs.length) : 0 });
  const byNet: Record<string, ReturnType<typeof pack>> = {};
  for (const n of NETS) { const xs = rows.filter((r) => r.network === n); if (xs.length) byNet[n] = pack(xs); }

  const top = [...rows].sort((a, b) => b.views - a.views).slice(0, 10).map((r) => ({
    title: (r.clip_id && titles.get(r.clip_id)?.title) || "(clip borrado)", network: r.network, views: r.views, likes: r.likes, comments: r.comments, shares: r.shares, publishedAt: r.published_at,
  }));

  const { data: hrs } = await db.from("best_hours").select("network,slot,score,posts,chosen,explore,updated_at").order("slot");
  const hours: Record<string, any[]> = {};
  (hrs ?? []).forEach((h: any) => (hours[h.network] ??= []).push(h));

  const { data: fol } = await db.from("page_followers").select("network,day,followers").gte("day", new Date(Date.now() - 30 * 86_400_000).toISOString().slice(0, 10)).order("day");
  const followers: Record<string, { now: number; delta7: number | null; delta30: number | null }> = {};
  for (const n of NETS) {
    const s = (fol ?? []).filter((f: any) => f.network === n) as { day: string; followers: number }[];
    if (!s.length) continue;
    const last = s[s.length - 1];
    const ago = (d: number) => { const t = Date.now() - d * 86_400_000; return [...s].reverse().find((x) => Date.parse(x.day) <= t) ?? null; };
    const a7 = ago(7), a30 = s[0];
    followers[n] = { now: last.followers, delta7: a7 ? last.followers - a7.followers : null, delta30: s.length > 1 ? last.followers - a30.followers : null };
  }

  const { data: next } = await db.from("posts").select("network,scheduled_at,clips(title)").eq("status", "queued").order("scheduled_at").limit(6);
  const { data: ws } = await db.from("worker_status").select("info").eq("id", 1).maybeSingle();
  const info = (ws?.info ?? {}) as Record<string, any>;
  const mature = rows.filter((r) => r.published_at && Date.now() - Date.parse(r.published_at) >= 24 * 3_600_000).length;
  const fetched = rows.map((r) => r.fetched_at).sort().pop() ?? null;

  return NextResponse.json({
    days, totals: pack(rows), byNet, top, hours, followers, upcoming: next ?? [],
    errors: rows.filter((r) => r.error).length, lastFetch: fetched,
    learning: { have: mature, need: Number(info.learn_min_posts) || 12, on: info.learn_slots ?? null, stats: info.stats ?? null },
    defaults: (process.env.POST_SLOTS || "12:30,19:00,21:30").split(",").map((s) => s.trim()).filter(Boolean),
  });
}
