import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { cleanTags, STYLE_IDS } from "@/lib/viral";
import type { Viral } from "@/lib/types";

export const dynamic = "force-dynamic";

// Hacerlo viral: aquí revisas cada clip (miniatura, título, hashtags, puntaje) antes de que salga.
// Lo que requiere trabajo pesado (rehacer miniatura, volver a analizar) lo deja como pedido en clips.viral_req y lo hace el worker (worker/studio.py).
const TABS: Record<string, string[]> = { review: ["review", "pending"], ready: ["ready"], approved: ["approved"], rejected: ["rejected"] };
const COLS = "id,title,source_id,start_sec,end_sec,viral_score,storage_path,size_bytes,description,hashtags,pack,thumb_path,thumb_b_path,viral,viral_status,scheduled_at,publish_status,created_at";
const NEW_COLS = ",thumb_choice,viral_req";
const need14 = (m: string) => (/viral_req|thumb_choice|viral_config/i.test(m) ? "Falta correr 0014_viral_estudio.sql en Supabase" : m);

type Row = {
  id: string; title: string; source_id: string | null; start_sec: number; end_sec: number; viral_score: number; storage_path: string | null; size_bytes: number | null;
  description: string | null; hashtags: string[] | null; pack: Record<string, any> | null; thumb_path: string | null; thumb_b_path: string | null;
  viral: Viral | null; viral_status: string | null; scheduled_at: string | null; publish_status: string | null; created_at: string;
  thumb_choice?: "a" | "b" | null; viral_req?: { action?: string; error?: string } | null;
};

export async function GET(req: Request) {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, clips: [], counts: {}, config: { require_approval: false } });
  const tab = new URL(req.url).searchParams.get("tab") ?? "review";
  const statuses = TABS[tab] ?? TABS.review;

  // 1) conteos por pestaña (últimos 30 días)
  const since = new Date(Date.now() - 30 * 86_400_000).toISOString();
  const { data: all, error: e0 } = await db.from("clips").select("viral_status").not("viral_status", "is", null).gte("created_at", since).limit(2000);
  if (e0) return NextResponse.json({ error: /viral_status/i.test(e0.message) ? "Falta correr 0009_viral.sql en Supabase" : e0.message }, { status: 500 });
  const counts: Record<string, number> = { review: 0, ready: 0, approved: 0, rejected: 0 };
  for (const r of (all ?? []) as { viral_status: string }[]) {
    const k = r.viral_status === "pending" ? "review" : r.viral_status;
    if (k in counts) counts[k]++;
  }

  // 2) los clips de la pestaña (con las columnas de la migración 0014 si ya existe)
  let rows: Row[] | null = null;
  let migrated = true;
  for (const cols of [COLS + NEW_COLS, COLS]) {
    const r = await db.from("clips").select(cols).in("viral_status", statuses).order("created_at", { ascending: false }).limit(30);
    if (!r.error) { rows = r.data as unknown as Row[]; migrated = cols.includes("viral_req"); break; }
    migrated = false;
    if (cols === COLS) return NextResponse.json({ error: r.error.message }, { status: 500 });
  }
  rows = rows ?? [];

  // 3) URLs firmadas solo de lo que se muestra
  const paths = rows.flatMap((r) => [r.storage_path, r.thumb_path, r.thumb_b_path]).filter((p): p is string => !!p);
  const url = new Map<string, string>();
  if (paths.length) {
    const s = await db.storage.from("clips").createSignedUrls(paths, 3600);
    s.data?.forEach((x) => x.path && x.signedUrl && url.set(x.path, x.signedUrl));
  }

  // 4) dónde está ya en cola
  const posts = new Map<string, { network: string; status: string; at: string | null }[]>();
  if (rows.length) {
    const { data: ps } = await db.from("posts").select("clip_id,network,status,scheduled_at").in("clip_id", rows.map((r) => r.id));
    (ps ?? []).forEach((p: any) => posts.set(p.clip_id, [...(posts.get(p.clip_id) ?? []), { network: p.network, status: p.status, at: p.scheduled_at }]));
  }

  const { data: cfg } = await db.from("viral_config").select("require_approval").eq("id", 1).maybeSingle();

  const clips = rows.map((r) => ({
    id: r.id, title: r.title, seconds: Math.round(Number(r.end_sec) - Number(r.start_sec)), score: r.viral_score, sizeMb: Math.round(((r.size_bytes ?? 0) / 1048576) * 10) / 10,
    status: r.viral_status, viral: r.viral ?? null, hashtags: r.hashtags ?? r.viral?.hashtags ?? [], description: r.description ?? "",
    videoUrl: r.storage_path ? url.get(r.storage_path) : undefined,
    thumbA: r.thumb_path ? url.get(r.thumb_path) : undefined, thumbB: r.thumb_b_path ? url.get(r.thumb_b_path) : undefined,
    thumbChoice: r.thumb_choice === "b" && r.thumb_b_path ? "b" : "a",
    busy: !!(r.viral_req && r.viral_req.action && !r.viral_req.error), reqAction: r.viral_req?.action ?? null, reqError: r.viral_req?.error ?? null,
    posts: posts.get(r.id) ?? [], publishStatus: r.publish_status, scheduledAt: r.scheduled_at, createdAt: r.created_at,
  }));
  return NextResponse.json({ clips, counts, config: { require_approval: !!cfg?.require_approval }, migrated, tab });
}

const slotOf = (a: any) => {
  if (!a || typeof a !== "object") return null;
  const text = String(a.text ?? "").split(/\s+/).filter(Boolean).join(" ").slice(0, 40);
  const t = a.time === null || a.time === undefined || a.time === "" ? null : Number(a.time);
  const style = String(a.style ?? "").toLowerCase();
  return { text, time: t !== null && Number.isFinite(t) && t >= 0 && t <= 600 ? Math.round(t * 100) / 100 : null, style: STYLE_IDS.includes(style) ? style : "" };
};

export async function POST(req: Request) {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const b = await req.json().catch(() => ({}));
  const action = String(b.action ?? "");
  const fail = (m: string, status = 400) => NextResponse.json({ error: m }, { status });

  // ---- ajustes y acciones en bloque
  if (action === "config") {
    const { error } = await db.from("viral_config").upsert({ id: 1, require_approval: !!b.require_approval, updated_at: new Date().toISOString() });
    return error ? fail(need14(error.message), 500) : NextResponse.json({ ok: true });
  }
  if (action === "approve_ready") {
    const { data } = await db.from("clips").select("id,viral").eq("viral_status", "ready").gte("created_at", new Date(Date.now() - 30 * 86_400_000).toISOString()).limit(200);
    const ids = ((data ?? []) as { id: string; viral: Viral | null }[]).filter((c) => !(c.viral?.risks?.length)).map((c) => c.id);   // los que traen riesgo los decides tú uno por uno
    if (ids.length) {
      const { error } = await db.from("clips").update({ viral_status: "approved" }).in("id", ids);
      if (error) return fail(error.message, 500);
    }
    return NextResponse.json({ ok: true, approved: ids.length });
  }

  // ---- acciones sobre un clip
  const id = String(b.id ?? "");
  if (!/^[0-9a-f-]{20,40}$/i.test(id)) return fail("Falta el clip");
  const sel = await db.from("clips").select("*").eq("id", id).maybeSingle();
  if (sel.error || !sel.data) return fail("Clip no encontrado", 404);
  const clip = sel.data as Row;
  const set = async (upd: Record<string, unknown>) => {
    const { error } = await db.from("clips").update(upd).eq("id", id);
    return error ? fail(need14(error.message), 500) : NextResponse.json({ ok: true });
  };

  if (action === "approve") return set({ viral_status: "approved" });
  if (action === "reject") return set({ viral_status: "rejected" });
  if (action === "reopen") return set({ viral_status: "review" });

  if (action === "choose_thumb") {
    if (b.choice !== "a" && b.choice !== "b") return fail("Elige a o b");
    if (b.choice === "b" && !clip.thumb_b_path) return fail("Este clip no tiene miniatura B");
    return set({ thumb_choice: b.choice });
  }

  if (action === "edit") {
    const upd: Record<string, unknown> = {};
    const pack = clip.pack && typeof clip.pack === "object" ? { ...clip.pack } : null;
    if (typeof b.title === "string") {
      const t = b.title.split(/\s+/).filter(Boolean).join(" ").slice(0, 80);
      if (t.length < 3) return fail("El título es muy corto");
      upd.title = t;
      if (pack?.shorts && typeof pack.shorts === "object") pack.shorts = { ...pack.shorts, title: t.slice(0, 70) };
    }
    if (b.hashtags !== undefined) {
      const tags = cleanTags(b.hashtags, 8);
      upd.hashtags = tags;
      if (pack) {
        for (const [net, cap] of [["tiktok", 5], ["reels", 5]] as const) if (pack[net] && typeof pack[net] === "object") pack[net] = { ...pack[net], hashtags: tags.slice(0, cap) };
        if (pack.shorts && typeof pack.shorts === "object") pack.shorts = { ...pack.shorts, hashtags: ["#Shorts", ...tags.filter((t) => t.toLowerCase() !== "#shorts")].slice(0, 4) };
      }
    }
    if (typeof b.description === "string") upd.description = b.description.trim().slice(0, 2200);
    if (!Object.keys(upd).length) return fail("Nada que cambiar");
    if (pack) upd.pack = pack;
    return set(upd);
  }

  if (action === "thumbs" || action === "reanalyze") {
    if (clip.viral_req && clip.viral_req.action && !clip.viral_req.error) return fail("El worker ya está trabajando en este clip", 409);
    if (action === "thumbs") {
      if (!clip.storage_path) return fail("Este clip no tiene archivo");
      const a = slotOf(b.a), bb = slotOf(b.b);
      if (!a && !bb) return fail("Nada que rehacer");
      return set({ viral_req: { action: "thumbs", ...(a ? { a } : {}), ...(bb ? { b: bb } : {}), at: new Date().toISOString() } });
    }
    return set({ viral_req: { action: "reanalyze", at: new Date().toISOString() } });
  }
  return fail("Acción desconocida");
}
