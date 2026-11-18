import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

// Conectar cuentas: guarda las llaves de Facebook, Instagram y YouTube (tabla connections). Nunca devuelve una llave completa.
// Espejo de worker/connections.py (FIELDS).
const FIELDS: Record<string, string[]> = {
  facebook: ["page_id", "page_token"],
  instagram: ["user_id", "token"],
  youtube: ["client_id", "client_secret", "refresh_token", "api_key"],
};
const SECRET = new Set(["page_token", "token", "client_secret", "refresh_token", "api_key"]);
const msg = (m: string) => (/connections/i.test(m) ? "Falta correr 0013_conexiones.sql en Supabase" : m);
const FB_API = "https://graph.facebook.com/v21.0";
const mask = (k: string, v: string) => (!v ? "" : SECRET.has(k) ? "••••" + v.slice(-4) : v);

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const { data, error } = await db.from("connections").select("network,data,updated_at");
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  const { data: ws } = await db.from("worker_status").select("info,seen_at").eq("id", 1).maybeSingle();
  const info = (ws?.info ?? {}) as { networks?: string[] };
  const items: Record<string, { saved: Record<string, string>; updatedAt: string | null; pageName?: string; pagePhoto?: string }> = {};
  for (const n of Object.keys(FIELDS)) {
    const row = (data ?? []).find((r: any) => r.network === n);
    const d = (row?.data ?? {}) as Record<string, string>;
    const item: any = { saved: Object.fromEntries(FIELDS[n].map((k) => [k, mask(k, String(d[k] ?? ""))])), updatedAt: row?.updated_at ?? null };
    // Para Facebook: obtener nombre y foto de la página si hay token
    if (n === "facebook" && d.page_id && d.page_token) {
      try {
        const r = await fetch(`${FB_API}/${d.page_id}?fields=name,picture{url}&access_token=${encodeURIComponent(d.page_token)}`, { cache: "no-store" });
        if (r.ok) {
          const j = await r.json();
          item.pageName = j.name ?? null;
          item.pagePhoto = j.picture?.data?.url ?? null;
        }
      } catch { /* ignore */ }
    }
    items[n] = item;
  }
  return NextResponse.json({ items, connected: info.networks ?? [], seenAt: ws?.seen_at ?? null });
}

/** fields: solo los campos que escribas; uno vacío NO borra el que ya estaba guardado. */
export async function POST(req: Request) {
  const b = await req.json().catch(() => ({}));
  const net = String(b.network ?? "");
  if (!FIELDS[net]) return NextResponse.json({ error: "Red no válida" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const { data: cur, error: e0 } = await db.from("connections").select("data").eq("network", net).maybeSingle();
  if (e0) return NextResponse.json({ error: msg(e0.message) }, { status: 500 });
  const merged: Record<string, string> = { ...((cur?.data ?? {}) as Record<string, string>) };
  for (const k of FIELDS[net]) {
    const v = typeof b.fields?.[k] === "string" ? b.fields[k].trim().slice(0, 1000) : "";
    if (v) merged[k] = v;
  }
  if (net === "facebook" && merged.page_id && !/^\d{5,}$/.test(merged.page_id)) return NextResponse.json({ error: "El ID de la página debe ser solo números" }, { status: 400 });
  if (net === "instagram" && merged.user_id && !/^\d{5,}$/.test(merged.user_id)) return NextResponse.json({ error: "El ID de Instagram debe ser solo números" }, { status: 400 });
  // Para Facebook: verificar la página y obtener nombre/foto antes de guardar
  let pageInfo: { name?: string; photo?: string } = {};
  if (net === "facebook" && merged.page_id && merged.page_token) {
    try {
      const r = await fetch(`${FB_API}/${merged.page_id}?fields=name,picture{url}&access_token=${encodeURIComponent(merged.page_token)}`, { cache: "no-store" });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        return NextResponse.json({ error: `Facebook rechazó el token o el ID de página: ${j?.error?.message ?? r.statusText}` }, { status: 400 });
      }
      const j = await r.json();
      pageInfo = { name: j.name, photo: j.picture?.data?.url };
    } catch (e: any) {
      return NextResponse.json({ error: `No se pudo verificar la página: ${e?.message ?? "error de red"}` }, { status: 400 });
    }
  }
  const { error } = await db.from("connections").upsert({ network: net, data: merged, updated_at: new Date().toISOString() });
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true, pageInfo });
}

export async function DELETE(req: Request) {
  const b = await req.json().catch(() => ({}));
  if (!FIELDS[String(b.network ?? "")]) return NextResponse.json({ error: "Red no válida" }, { status: 400 });
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const { error } = await db.from("connections").delete().eq("network", b.network);
  if (error) return NextResponse.json({ error: msg(error.message) }, { status: 500 });
  return NextResponse.json({ ok: true });
}
