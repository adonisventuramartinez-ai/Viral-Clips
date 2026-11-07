import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { loadClips, workerOnline } from "@/lib/clips";

export const dynamic = "force-dynamic";

// Estado del último directo: fuente, progreso, clips y momentos descartados.
export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, source: null, clips: [], rejected: [], worker: false });

  try {
    const worker = await workerOnline(db);
    const { data: source, error } = await db
      .from("sources")
      .select("id,title,url,status,error,progress,created_at")
      .eq("kind", "live")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    if (!source) return NextResponse.json({ source: null, clips: [], rejected: [], worker });

    const [clips, rej] = await Promise.all([
      loadClips(db, source.id),
      db.from("rejected_moments").select("title,score,reason").eq("source_id", source.id).order("created_at", { ascending: false }).limit(20),
    ]);
    return NextResponse.json({ source, clips, rejected: rej.data ?? [], worker });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}
