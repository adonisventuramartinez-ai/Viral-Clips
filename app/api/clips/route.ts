import { NextResponse } from "next/server";
import { serverClient } from "@/lib/supabase";
import { fmtTime } from "@/lib/format";
import type { Clip } from "@/lib/types";

export const dynamic = "force-dynamic";

type Row = {
  id: string;
  title: string;
  start_sec: number;
  end_sec: number;
  viral_score: number;
  reason: string | null;
  storage_path: string | null;
  size_bytes: number | null;
};

export async function GET() {
  const db = serverClient();
  if (!db) return NextResponse.json({ demo: true, clips: [], sources: [] });

  const [c, s] = await Promise.all([
    db.from("clips")
      .select("id,title,start_sec,end_sec,viral_score,reason,storage_path,size_bytes")
      .order("created_at", { ascending: false })
      .limit(200),
    db.from("sources")
      .select("id,title,url,status,error,created_at")
      .order("created_at", { ascending: false })
      .limit(20),
  ]);
  if (c.error) return NextResponse.json({ error: c.error.message }, { status: 500 });
  if (s.error) return NextResponse.json({ error: s.error.message }, { status: 500 });

  const rows = (c.data ?? []) as Row[];
  const paths = rows.map((r) => r.storage_path).filter((p): p is string => !!p);
  const play = new Map<string, string>();
  const dl = new Map<string, string>();
  if (paths.length) {
    const bucket = db.storage.from("clips");
    const [a, b] = await Promise.all([
      bucket.createSignedUrls(paths, 3600),
      bucket.createSignedUrls(paths, 3600, { download: true }),
    ]);
    a.data?.forEach((x) => x.path && x.signedUrl && play.set(x.path, x.signedUrl));
    b.data?.forEach((x) => x.path && x.signedUrl && dl.set(x.path, x.signedUrl));
  }

  const clips: Clip[] = rows.map((r) => ({
    id: r.id,
    title: r.title,
    start: fmtTime(r.start_sec),
    end: fmtTime(r.end_sec),
    score: r.viral_score,
    sizeMb: Math.round(((r.size_bytes ?? 0) / 1048576) * 10) / 10,
    captions: "",
    thumb: "",
    reason: r.reason ?? undefined,
    videoUrl: r.storage_path ? play.get(r.storage_path) : undefined,
    downloadUrl: r.storage_path ? dl.get(r.storage_path) : undefined,
  }));

  return NextResponse.json({ clips, sources: s.data ?? [] });
}
