import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

// Botón "Clip ahora": pide al worker cortar los últimos segundos del directo que está grabando.
export async function POST(req: Request) {
  const { source_id, seconds = 45 } = await req.json().catch(() => ({}));
  if (!source_id || typeof source_id !== "string") return NextResponse.json({ error: "Falta source_id" }, { status: 400 });
  const secs = Math.min(120, Math.max(15, Math.round(Number(seconds)) || 45));
  const db = serverClient();
  if (!db) return NextResponse.json({ ok: true, demo: true });

  const { data: src } = await db.from("sources").select("id,status,kind").eq("id", source_id).maybeSingle();
  if (!src || src.kind !== "live" || src.status !== "recording") {
    return NextResponse.json({ error: "El directo no está grabando ahora mismo" }, { status: 409 });
  }
  // evita spam: máximo 3 pedidos esperando a la vez
  const { count } = await db.from("live_commands").select("id", { count: "exact", head: true }).eq("source_id", source_id).eq("status", "pending");
  if ((count ?? 0) >= 3) return NextResponse.json({ error: "Ya hay 3 clips en camino, espera a que salgan" }, { status: 429 });

  const { error } = await db.from("live_commands").insert({ source_id, kind: "clip_now", seconds: secs });
  if (error) {
    const msg = /live_commands/i.test(error.message) ? "Falta ejecutar 0006_envivo.sql en Supabase" : error.message;
    return NextResponse.json({ error: msg }, { status: 500 });
  }
  return NextResponse.json({ ok: true });
}
