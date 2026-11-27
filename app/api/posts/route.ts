import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";

export const dynamic = "force-dynamic";

/** Cola de publicación: próximas y recientes, con el título del clip, más el estado de la cola automática según el worker. */
export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ error: "Supabase no está conectado" }, { status: 503 });
  const { data, error } = await db.from("posts")
    .select("id,network,status,scheduled_at,external_id,error,published_at,clip_id,clips(title,viral_score,viral)")
    .order("scheduled_at", { ascending: true }).limit(200);
  if (error) return NextResponse.json({ error: error.message.includes("posts") ? "Falta correr 0010_cola_publicacion.sql en Supabase" : error.message }, { status: 500 });
  const { data: ws } = await db.from("worker_status").select("info,seen_at").eq("id", 1).maybeSingle();
  return NextResponse.json({ posts: data ?? [], worker: ws?.info ?? {}, seenAt: ws?.seen_at ?? null });
}
