import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { loadClips, workerOnline } from "@/lib/clips";

export const dynamic = "force-dynamic";
export const revalidate = 0;
export const fetchCache = "force-no-store";

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, clips: [], sources: [] });

  try {
    const [clips, s, worker] = await Promise.all([
      loadClips(db),
      db.from("sources").select("id,title,url,status,error,created_at").order("created_at", { ascending: false }).limit(20),
      workerOnline(db),
    ]);
    if (s.error) return NextResponse.json({ error: s.error.message }, { status: 500 });
    return NextResponse.json({ clips, sources: s.data ?? [], worker });
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }
}
