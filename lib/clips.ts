import type { SupabaseClient } from "@supabase/supabase-js";
import { fmtTime } from "./format";
import type { Clip } from "./types";

type Row = {
  id: string;
  title: string;
  start_sec: number;
  end_sec: number;
  viral_score: number;
  reason: string | null;
  storage_path: string | null;
  size_bytes: number | null;
  is_public?: boolean | null;
};

const COLS = "id,title,start_sec,end_sec,viral_score,reason,storage_path,size_bytes";

/** Clips (más nuevos primero) con URLs firmadas para ver y descargar. sourceId opcional. */
export async function loadClips(db: SupabaseClient, sourceId?: string): Promise<Clip[]> {
  const q = (cols: string) => {
    const base = db.from("clips").select(cols);
    return (sourceId ? base.eq("source_id", sourceId) : base).order("created_at", { ascending: false }).limit(200);
  };
  let { data, error } = await q(COLS + ",is_public");
  if (error) ({ data, error } = await q(COLS)); // aún no corriste la migración 0004: funciona sin is_public
  if (error) throw new Error(error.message);

  const rows = (data ?? []) as unknown as Row[];
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

  return rows.map((r) => ({
    id: r.id,
    title: r.title,
    start: fmtTime(r.start_sec),
    end: fmtTime(r.end_sec),
    score: r.viral_score,
    sizeMb: Math.round(((r.size_bytes ?? 0) / 1048576) * 10) / 10,
    captions: "",
    thumb: "",
    reason: r.reason ?? undefined,
    isPublic: r.is_public ?? true,
    videoUrl: r.storage_path ? play.get(r.storage_path) : undefined,
    downloadUrl: r.storage_path ? dl.get(r.storage_path) : undefined,
  }));
}

/** true si el worker dio señales de vida en los últimos 45 s. */
export async function workerOnline(db: SupabaseClient): Promise<boolean> {
  const { data } = await db.from("worker_status").select("seen_at").eq("id", 1).maybeSingle();
  if (!data) return false;
  return Date.now() - new Date(data.seen_at as string).getTime() < 45000;
}
